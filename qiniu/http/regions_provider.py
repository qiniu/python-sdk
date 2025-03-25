import abc
import datetime
import errno
import itertools
from collections import namedtuple
import logging
import tempfile
import os
import shutil
import threading

from qiniu.compat import json, b as to_bytes, is_windows, is_linux, is_macos
from qiniu.utils import io_md5, dt2ts

from .endpoint import Endpoint
from .region import Region, ServiceName
from .default_client import qn_http_client
from .middleware import RetryDomainsMiddleware
from .single_flight import SingleFlight


class RegionsProvider:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __iter__(self):
        """
        Returns
        -------
        Generator[Region, None, None]
        """


class MutableRegionsProvider(RegionsProvider):
    @abc.abstractmethod
    def set_regions(self, regions):
        """
        Parameters
        ----------
        regions: list[Region]
        """


# --- serializers for QueryRegionsProvider ---

def _get_region_from_query(data, **kwargs):
    preferred_scheme = kwargs.get('preferred_scheme')
    if not preferred_scheme:
        preferred_scheme = 'http'

    domain_path_map = {
        k: (k.value, 'domains')
        for k in ServiceName
        if k not in [ServiceName.UP_ACC]
    }
    domain_path_map[ServiceName.UP_ACC] = ('up', 'acc_domains')

    services = {
        # sn service name, dsn data service name
        sn: [
            Endpoint(h, default_scheme=preferred_scheme)
            for h in data.get(dsn, {}).get(k, [])
        ]
        for sn, (dsn, k) in domain_path_map.items()
    }

    return Region(
        region_id=data.get('region'),
        s3_region_id=data.get('s3', {}).get('region_alias', None),
        services=services,
        ttl=data.get('ttl', None)
    )


_query_regions_single_flight = SingleFlight()


class QueryRegionsProvider(RegionsProvider):
    def __init__(
        self,
        access_key,
        bucket_name,
        endpoints_provider,
        preferred_scheme='http',
        max_retry_times_per_endpoint=1,
    ):
        """
        Parameters
        ----------
        access_key: str
        bucket_name: str
        endpoints_provider: Iterable[Endpoint]
        preferred_scheme: str
        max_retry_times_per_endpoint: int
        """
        self.access_key = access_key
        self.bucket_name = bucket_name
        self.endpoints_provider = endpoints_provider
        self.preferred_scheme = preferred_scheme
        self.max_retry_times_per_endpoint = max_retry_times_per_endpoint

    def __iter__(self):
        endpoints_md5 = io_md5([
            to_bytes(e.host) for e in self.endpoints_provider
        ])
        flight_key = ':'.join([
            endpoints_md5,
            self.access_key,
            self.bucket_name
        ])
        regions = _query_regions_single_flight.do(flight_key, self.__fetch_regions)
        # change to `yield from` when min version of python update to >= 3.3
        for r in regions:
            yield r

    def __fetch_regions(self):
        endpoints = list(self.endpoints_provider)
        if not endpoints:
            raise ValueError('There aren\'t any available endpoints to query regions')
        endpoint, alternative_endpoints = endpoints[0], endpoints[1:]

        url = '{0}/v4/query?ak={1}&bucket={2}'.format(endpoint.get_value(), self.access_key, self.bucket_name)
        ret, resp = qn_http_client.get(
            url,
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=[e.host for e in alternative_endpoints],
                    max_retry_times=self.max_retry_times_per_endpoint
                )
            ]
        )

        if not resp.ok():
            raise RuntimeError(
                (
                    'Query regions failed with '
                    'HTTP Status Code {0}, '
                    'Body {1}'
                ).format(resp.status_code, resp.text_body)
            )

        return [
            _get_region_from_query(d, preferred_scheme=self.preferred_scheme)
            for d in ret.get('hosts', [])
        ]


# --- helpers for CachedRegionsProvider ---
class FileAlreadyLocked(RuntimeError):
    def __init__(self, message):
        super(FileAlreadyLocked, self).__init__(message)


_file_threading_lockers_lock = threading.Lock()
_file_threading_lockers = {}


class _FileThreadingLocker:
    def __init__(self, fd):
        self._fd = fd

    def __enter__(self):
        with _file_threading_lockers_lock:
            global _file_threading_lockers
            threading_lock = _file_threading_lockers.get(self._file_path, threading.Lock())
            # Could use keyword style `acquire(blocking=False)` when min version of python update to >= 3
            if not threading_lock.acquire(False):
                raise FileAlreadyLocked('File {0} already locked'.format(self._file_path))
            _file_threading_lockers[self._file_path] = threading_lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        with _file_threading_lockers_lock:
            global _file_threading_lockers
            threading_lock = _file_threading_lockers.get(self._file_path)
            if threading_lock and threading_lock.locked():
                threading_lock.release()
                del _file_threading_lockers[self._file_path]

    @property
    def _file_path(self):
        return self._fd.name


if is_linux or is_macos:
    import fcntl

    # Use subclass of _FileThreadingLocker when min version of python update to >= 3
    class _FileLocker:
        def __init__(self, fd):
            self._fd = fd

        def __enter__(self):
            try:
                fcntl.lockf(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                # Use `raise ... from ...` when min version of python update to >= 3
                raise FileAlreadyLocked('File {0} already locked'.format(self._file_path))

        def __exit__(self, exc_type, exc_val, exc_tb):
            fcntl.lockf(self._fd, fcntl.LOCK_UN)

        @property
        def _file_path(self):
            return self._fd.name

elif is_windows:
    import msvcrt

    class _FileLocker:
        def __init__(self, fd):
            self._fd = fd
            self._lock_fd = None
            self._already_locked = False

        def __enter__(self):
            try:
                self._lock_fd = open(self._lock_file_path, 'w')
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_LOCK | msvcrt.LK_NBLCK, 1)
            except OSError:
                self._already_locked = True
                raise FileAlreadyLocked('File {0} already locked'.format(self._file_path))

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._already_locked:
                if self._lock_fd:
                    self._lock_fd.close()
                return

            try:
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._lock_fd.close()
                os.remove(self._lock_file_path)

        @property
        def _file_path(self):
            return self._fd.name

        @property
        def _lock_file_path(self):
            """
            Returns
            -------
            str
            """
            return self._file_path + '.lock'

else:
    class _FileLocker:
        def __init__(self, fd):
            self._fd = fd
            self._already_locked = False

        def __enter__(self):
            try:
                # Atomic file creation
                open_flags = os.O_EXCL | os.O_RDWR | os.O_CREAT
                fd = os.open(self._lock_file_path, open_flags)
                os.close(fd)
            except OSError:
                self._already_locked = True
                raise FileAlreadyLocked('File {0} already locked'.format(self._file_path))

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self._already_locked:
                return
            try:
                os.remove(self._lock_file_path)
            except OSError:
                pass

        @property
        def _file_path(self):
            return self._fd.name

        @property
        def _lock_file_path(self):
            """
            Returns
            -------
            str
            """
            return self._file_path + '.lock'


# use dataclass instead namedtuple if min version of python update to 3.7
CacheScope = namedtuple(
    'CacheScope',
    [
        'memo_cache',
        'persist_path',
        'last_shrink_at',
        'shrink_interval',
        'should_shrink_expired_regions',
        'memo_cache_lock'
    ]
)


_global_cache_scope = CacheScope(
    memo_cache={},
    persist_path=os.path.join(
        tempfile.gettempdir(),
        'qn-py-sdk',
        'regions-cache.jsonl'
    ),
    last_shrink_at=datetime.datetime.fromtimestamp(0),
    shrink_interval=datetime.timedelta(days=1),
    should_shrink_expired_regions=False,
    memo_cache_lock=threading.Lock()
)


# --- serializers for CachedRegionsProvider ---

_PersistedEndpoint = namedtuple(
    'PersistedEndpoint',
    [
        'host',
        'defaultScheme'
    ]
)


def _persist_endpoint(endpoint):
    """
    Parameters
    ----------
    endpoint: Endpoint

    Returns
    -------
    dict
    """
    return _PersistedEndpoint(
        defaultScheme=endpoint.default_scheme,
        host=endpoint.host
    )._asdict()


def _get_endpoint_from_persisted(data):
    """
    Parameters
    ----------
    data: dict

    Returns
    -------
    Endpoint
    """
    persisted_endpoint = _PersistedEndpoint(**data)
    return Endpoint(
        persisted_endpoint.host,
        default_scheme=persisted_endpoint.defaultScheme
    )


_PersistedRegion = namedtuple(
    'PersistedRegion',
    [
        'regionId',
        's3RegionId',
        'services',
        'ttl',
        'createTime'
    ]
)


def _persist_region(region):
    """
    Parameters
    ----------
    region: Region

    Returns
    -------
    dict
    """
    return _PersistedRegion(
        regionId=region.region_id,
        s3RegionId=region.s3_region_id,
        services={
            # The StrEnum not available in python < 3.11
            # so need stringify the key manually
            k.value if isinstance(k, ServiceName) else k: [
                _persist_endpoint(e)
                for e in v
            ]
            for k, v in region.services.items()
        },
        ttl=region.ttl,
        # use datetime.datetime.timestamp() when min version of python >= 3
        createTime=dt2ts(region.create_time)
    )._asdict()


def _get_region_from_persisted(data):
    """
    Parameters
    ----------
    data: dict

    Returns
    -------
    Region
    """
    def _get_service_name(k):
        try:
            return ServiceName(k)
        except ValueError:
            return k

    persisted_region = _PersistedRegion(**data)

    return Region(
        region_id=persisted_region.regionId,
        s3_region_id=persisted_region.s3RegionId,
        services={
            # The StrEnum not available in python < 3.11
            # so need parse the key manually
            _get_service_name(k): [
                _get_endpoint_from_persisted(d)
                for d in v
            ]
            for k, v in persisted_region.services.items()
        },
        ttl=persisted_region.ttl,
        create_time=datetime.datetime.fromtimestamp(persisted_region.createTime / 1000)
    )


def _parse_persisted_regions(persisted_data):
    """
    Parameters
    ----------
    persisted_data: str

    Returns
    -------
    cache_key: str
    regions: list[Region]
    """
    parsed_data = json.loads(persisted_data)
    regions = [
        _get_region_from_persisted(d)
        for d in parsed_data.get('regions', [])
    ]
    return parsed_data.get('cacheKey'), regions


def _walk_persist_cache_file(persist_path, ignore_parse_error=True):
    """
    Parameters
    ----------
    persist_path: str
    ignore_parse_error: bool

    Returns
    -------
    Iterable[(str, list[Region])]
    """
    if not os.access(persist_path, os.R_OK):
        return

    with open(persist_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                cache_key, regions = _parse_persisted_regions(line.strip())
                yield cache_key, regions
            except Exception as err:
                if not ignore_parse_error:
                    raise err


def _merge_regions(*args):
    """
    merge two regions by region id.
    if the same region id, the last create region will be keep.
    Parameters
    ----------
    args: list[Region]

    Returns
    -------
    list[Region]
    """
    regions_dict = {}

    for r in itertools.chain(*args):
        if r.region_id not in regions_dict:
            regions_dict[r.region_id] = r
        else:
            if r.create_time > regions_dict[r.region_id].create_time:
                regions_dict[r.region_id] = r

    return regions_dict.values()


class CachedRegionsProvider(MutableRegionsProvider):
    def __init__(
        self,
        cache_key,
        base_regions_provider,
        **kwargs
    ):
        """
        Parameters
        ----------
        cache_key: str
        base_regions_provider: Iterable[Region]
        kwargs
            persist_path: str
            shrink_interval: datetime.timedelta
            should_shrink_expired_regions: bool
        """
        self.cache_key = cache_key
        self.base_regions_provider = base_regions_provider

        persist_path = kwargs.get('persist_path', None)
        last_shrink_at = datetime.datetime.fromtimestamp(0)
        if persist_path is None:
            cache_dir = os.path.dirname(_global_cache_scope.persist_path)
            try:
                # make sure the cache dir is available for all users.
                # we can not use the '/tmp' dir directly on linux,
                # because the permission is 0o1777
                if not os.path.exists(cache_dir):
                    # os.makedirs have no exists_ok parameter in python 2.7
                    os.makedirs(cache_dir)
                    os.chmod(cache_dir, 0o777)
                persist_path = _global_cache_scope.persist_path
                last_shrink_at = _global_cache_scope.last_shrink_at
            except Exception as err:
                if isinstance(err, OSError) and err.errno == errno.EEXIST:
                    persist_path = _global_cache_scope.persist_path
                    last_shrink_at = _global_cache_scope.last_shrink_at
                else:
                    logging.warning(
                        'failed to create cache dir %s. error: %s', cache_dir, err)

        shrink_interval = kwargs.get('shrink_interval', None)
        if shrink_interval is None:
            shrink_interval = _global_cache_scope.shrink_interval

        should_shrink_expired_regions = kwargs.get('should_shrink_expired_regions', None)
        if should_shrink_expired_regions is None:
            should_shrink_expired_regions = _global_cache_scope.should_shrink_expired_regions

        self._cache_scope = _global_cache_scope._replace(
            persist_path=persist_path,
            last_shrink_at=last_shrink_at,
            shrink_interval=shrink_interval,
            should_shrink_expired_regions=should_shrink_expired_regions
        )

    def __iter__(self):
        if self.__should_shrink:
            try:
                self.__shrink_cache()
            except Exception as err:
                logging.warning('failed to shrink cache. error: %s', err)

        get_regions_fns = [
            self.__get_regions_from_memo,
            self.__get_regions_from_file,
            self.__get_regions_from_base_provider
        ]

        # set the fallback to None for raise errors when failed
        regions = None
        for get_regions in get_regions_fns:
            regions = get_regions(fallback=regions)
            if regions and all(r.is_live for r in regions):
                break

        # change to `yield from` when min version of python update to >= 3.3
        for r in regions:
            yield r

    def set_regions(self, regions):
        """
        Parameters
        ----------
        regions: list[Region]
        """
        with self._cache_scope.memo_cache_lock:
            self._cache_scope.memo_cache[self.cache_key] = regions

        if not self._cache_scope.persist_path:
            return

        try:
            with open(self._cache_scope.persist_path, 'a') as f:
                f.write(json.dumps({
                    'cacheKey': self.cache_key,
                    'regions': [_persist_region(r) for r in regions]
                }) + os.linesep)
        except Exception as err:
            logging.warning('failed to cache regions result to file. error: %s', err)

    @property
    def persist_path(self):
        """
        Returns
        -------
        str
        """
        return self._cache_scope.persist_path

    @persist_path.setter
    def persist_path(self, value):
        """
        Parameters
        ----------
        value: str
        """
        if value == self._cache_scope.persist_path:
            return
        self._cache_scope = self._cache_scope._replace(
            persist_path=value,
            last_shrink_at=datetime.datetime.fromtimestamp(0)
        )

    @property
    def last_shrink_at(self):
        """
        Returns
        -------
        datetime.datetime
        """
        # copy the datetime make sure it is read-only
        return self._cache_scope.last_shrink_at.replace()

    @property
    def shrink_interval(self):
        """
        Returns
        -------
        datetime.timedelta
        """
        return self._cache_scope.shrink_interval

    @shrink_interval.setter
    def shrink_interval(self, value):
        """
        Parameters
        ----------
        value: datetime.timedelta
        """
        self._cache_scope = self._cache_scope._replace(
            shrink_interval=value
        )

    @property
    def should_shrink_expired_regions(self):
        """
        Returns
        -------
        bool
        """
        return self._cache_scope.should_shrink_expired_regions

    @should_shrink_expired_regions.setter
    def should_shrink_expired_regions(self, value):
        """
        Parameters
        ----------
        value: bool
        """
        self._cache_scope = self._cache_scope._replace(
            should_shrink_expired_regions=value
        )

    def __get_regions_from_memo(self, fallback=None):
        """
        Parameters
        ----------
        fallback: list[Region]

        Returns
        -------
        list[Region]
        """
        regions = self._cache_scope.memo_cache.get(self.cache_key)

        if regions:
            return regions

        return fallback

    def __get_regions_from_file(self, fallback=None):
        """
        Parameters
        ----------
        fallback: list[Region]

        Returns
        -------
        list[Region]
        """
        if not self._cache_scope.persist_path:
            return fallback

        try:
            self.__flush_file_cache_to_memo()
        except Exception as err:
            if fallback is not None:
                return fallback
            else:
                raise err

        return self.__get_regions_from_memo(fallback)

    def __get_regions_from_base_provider(self, fallback=None):
        """
        Parameters
        ----------
        fallback: list[Region]

        Returns
        -------
        list[Region]
        """
        try:
            regions = list(self.base_regions_provider)
        except Exception as err:
            if fallback is not None:
                return fallback
            else:
                raise err
        self.set_regions(regions)
        return regions

    def __flush_file_cache_to_memo(self):
        for cache_key, regions in _walk_persist_cache_file(
            persist_path=self._cache_scope.persist_path
        ):
            if cache_key not in self._cache_scope.memo_cache:
                self._cache_scope.memo_cache[cache_key] = regions
                return
            memo_regions = self._cache_scope.memo_cache[cache_key]
            self._cache_scope.memo_cache[cache_key] = _merge_regions(
                memo_regions,
                regions
            )

    @property
    def __should_shrink(self):
        """
        Returns
        -------
        bool
        """
        return datetime.datetime.now() - self._cache_scope.last_shrink_at > self._cache_scope.shrink_interval

    def __shrink_cache(self):
        # shrink memory cache
        if self._cache_scope.should_shrink_expired_regions:
            memo_cache_old = self._cache_scope.memo_cache.copy()
            # Could use keyword style `acquire(blocking=False)` when min version of python update to >= 3
            if self._cache_scope.memo_cache_lock.acquire(False):
                try:
                    for k, regions in memo_cache_old.items():
                        live_regions = [r for r in regions if r.is_live]
                        if live_regions:
                            self._cache_scope.memo_cache[k] = live_regions
                        else:
                            del self._cache_scope.memo_cache[k]
                finally:
                    self._cache_scope.memo_cache_lock.release()

        # shrink file cache
        if not self._cache_scope.persist_path:
            self._cache_scope = self._cache_scope._replace(
                last_shrink_at=datetime.datetime.now()
            )
            return

        shrink_file_path = self._cache_scope.persist_path + '.shrink'
        try:
            with open(shrink_file_path, 'a') as f, _FileThreadingLocker(f), _FileLocker(f):
                # filter data
                shrunk_cache = {}
                for cache_key, regions in _walk_persist_cache_file(
                    persist_path=self._cache_scope.persist_path
                ):
                    kept_regions = regions
                    if self._cache_scope.should_shrink_expired_regions:
                        kept_regions = [
                            r for r in kept_regions if r.is_live
                        ]

                    if cache_key not in shrunk_cache:
                        shrunk_cache[cache_key] = kept_regions
                    else:
                        shrunk_cache[cache_key] = _merge_regions(
                            shrunk_cache[cache_key],
                            kept_regions
                        )

                # write data
                for cache_key, regions in shrunk_cache.items():
                    f.write(
                        json.dumps(
                            {
                                'cacheKey': cache_key,
                                'regions': [_persist_region(r) for r in regions]
                            }
                        ) + os.linesep
                    )

                # make the cache file available for all users
                if is_linux or is_macos:
                    os.chmod(shrink_file_path, 0o666)

                # rename file
                if is_windows:
                    # windows must close first, or will raise permission error
                    # be careful to do something with the file after this
                    f.close()
                shutil.move(shrink_file_path, self._cache_scope.persist_path)

                # update last shrink time
                self._cache_scope = self._cache_scope._replace(
                    last_shrink_at=datetime.datetime.now()
                )
                global _global_cache_scope
                if _global_cache_scope.persist_path == self._cache_scope.persist_path:
                    _global_cache_scope = _global_cache_scope._replace(
                        last_shrink_at=self._cache_scope.last_shrink_at
                    )

        except FileAlreadyLocked:
            # skip file shrink by another running
            pass


def get_default_regions_provider(
    query_endpoints_provider,
    access_key,
    bucket_name,
    accelerate_uploading=False,
    force_query=False,
    **kwargs
):
    """
    Parameters
    ----------
    query_endpoints_provider: Iterable[Endpoint]
    access_key: str
    bucket_name: str
    accelerate_uploading: bool
    force_query: bool
    kwargs
        preferred_scheme: str
            option of QueryRegionsProvider
        max_retry_times_per_endpoint: int
            option of QueryRegionsProvider
        persist_path: str
            option of CachedRegionsProvider
        shrink_interval: datetime.timedelta
            option of CachedRegionsProvider
        should_shrink_expired_regions: bool
            option of CachedRegionsProvider

    Returns
    -------
    Iterable[Region]
    """
    query_regions_provider_opts = {
        'access_key': access_key,
        'bucket_name': bucket_name,
        'endpoints_provider': query_endpoints_provider,
    }
    query_regions_provider_opts.update({
        k: v
        for k, v in kwargs.items()
        if k in ['preferred_scheme', 'max_retry_times_per_endpoint']
    })

    query_regions_provider = QueryRegionsProvider(**query_regions_provider_opts)

    if force_query:
        return query_regions_provider

    query_endpoints = list(query_endpoints_provider)

    endpoints_md5 = io_md5([
        to_bytes(e.host) for e in query_endpoints
    ])
    cache_key = ':'.join([
        endpoints_md5,
        access_key,
        bucket_name,
        'true' if accelerate_uploading else 'false'
    ])

    cached_regions_provider_opts = {
        'cache_key': cache_key,
        'base_regions_provider': query_regions_provider,
    }
    cached_regions_provider_opts.update({
        k: v
        for k, v in kwargs.items()
        if k in [
            'persist_path',
            'shrink_interval',
            'should_shrink_expired_regions'
        ]
    })

    return CachedRegionsProvider(
        **cached_regions_provider_opts
    )
