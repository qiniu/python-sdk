import abc
import datetime
import itertools
from collections import namedtuple
import logging
import tempfile
import os

from qiniu.compat import json, b as to_bytes
from qiniu.utils import io_md5

from .endpoint import Endpoint
from .region import Region, ServiceName
from .default_client import qn_http_client
from .middleware import RetryDomainsMiddleware


class RegionsProvider:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __iter__(self):
        """
        Returns
        -------
        list[Region]
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
    preferred_scheme = kwargs.get('preferred_scheme', 'https')

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


class QueryRegionsProvider(RegionsProvider):
    def __init__(
        self,
        access_key,
        bucket_name,
        endpoints_provider,
        preferred_scheme='https',
        max_retry_times_per_endpoint=1,
    ):
        self.access_key = access_key
        self.bucket_name = bucket_name
        self.endpoints_provider = endpoints_provider
        self.preferred_scheme = preferred_scheme
        self.max_retry_times_per_endpoint = max_retry_times_per_endpoint

    def __iter__(self):
        regions = self.__fetch_regions()
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


class _FileLocker:
    def __init__(self, origin_file):
        self._origin_file = origin_file

    def __enter__(self):
        if os.access(self.lock_file_path, os.R_OK | os.W_OK):
            raise FileAlreadyLocked('File {0} already locked'.format(self._origin_file))
        with open(self.lock_file_path, 'w'):
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.remove(self.lock_file_path)

    @property
    def lock_file_path(self):
        return self._origin_file + '.lock'


# use dataclass instead namedtuple if min version of python update to 3.7
CacheScope = namedtuple(
    'CacheScope',
    [
        'memo_cache',
        'persist_path',
        'last_shrink_at',
        'shrink_interval',
        'should_shrink_expired_regions'
    ]
)


_global_cache_scope = CacheScope(
    memo_cache={},
    persist_path=os.path.join(
        tempfile.gettempdir(),
        'qn-regions-cache.jsonl'
    ),
    last_shrink_at=datetime.datetime.fromtimestamp(0),
    shrink_interval=datetime.timedelta(-1),  # useless for now
    should_shrink_expired_regions=False
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
        createTime=int(float(region.create_time.strftime('%s.%f')) * 1000)
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
    parsed_data = json.loads(persisted_data)
    regions = [
        _get_region_from_persisted(d)
        for d in parsed_data.get('regions', [])
    ]
    return parsed_data.get('cache_key'), regions


def _walk_persist_cache_file(persist_path, ignore_parse_error=False):
    if not os.access(persist_path, os.R_OK):
        return

    with open(persist_path, 'r') as f:
        for line in f:
            try:
                cache_key, regions = _parse_persisted_regions(line)
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
        if persist_path is None:
            persist_path = _global_cache_scope.persist_path

        shrink_interval = kwargs.get('shrink_interval', None)
        if shrink_interval is None:
            shrink_interval = datetime.timedelta(days=1)

        should_shrink_expired_regions = kwargs.get('should_shrink_expired_regions', None)
        if should_shrink_expired_regions is None:
            should_shrink_expired_regions = False

        self._cache_scope = CacheScope(
            memo_cache=_global_cache_scope.memo_cache,
            persist_path=persist_path,
            last_shrink_at=datetime.datetime.fromtimestamp(0),
            shrink_interval=shrink_interval,
            should_shrink_expired_regions=should_shrink_expired_regions,
        )

    def __iter__(self):
        if self.__should_shrink:
            self.__shrink_cache()

        get_regions_fns = [
            self.__get_regions_from_memo,
            self.__get_regions_from_file,
            self.__get_regions_from_base_provider
        ]

        regions = None
        for get_regions in get_regions_fns:
            regions = get_regions(fallback=regions)
            if regions and all(r.is_live for r in regions):
                break

        # change to `yield from` when min version of python update to >= 3.3
        for r in regions:
            yield r

    def set_regions(self, regions):
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
            logging.warning('failed to cache regions result to file', err)

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
        self._cache_scope = self._cache_scope._replace(
            persist_path=value
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
            # ignore_parse_error=True
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
        return self._cache_scope.last_shrink_at + self._cache_scope.shrink_interval >= datetime.datetime.now()

    def __shrink_cache(self):
        # shrink memory cache
        if self._cache_scope.should_shrink_expired_regions:
            for k, regions in self._cache_scope.memo_cache.items():
                live_regions = [r.is_live for r in regions]
                if live_regions:
                    self._cache_scope.memo_cache[k] = live_regions

        # shrink file cache
        if not self._cache_scope.persist_path:
            self._cache_scope = self._cache_scope._replace(
                last_shrink_at=datetime.datetime.now()
            )
            return

        shrink_file_path = self._cache_scope.persist_path + '.shrink'
        try:
            with _FileLocker(shrink_file_path):
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
                with open(shrink_file_path, 'a') as f:
                    for cache_key, regions in shrunk_cache.items():
                        f.write(
                            json.dumps(
                                {
                                    'cacheKey': cache_key,
                                    'regions': [_persist_region(r) for r in regions]
                                }
                            ) + os.linesep
                        )

                # rename file
                os.rename(shrink_file_path, self._cache_scope.persist_path)
        except FileAlreadyLocked:
            pass
        finally:
            self._cache_scope = self._cache_scope._replace(
                last_shrink_at=datetime.datetime.now()
            )


def get_default_regions_provider(
    query_endpoints_provider,
    access_key,
    bucket_name,
    accelerate_uploading,
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
