# -*- coding: utf-8 -*-
import functools
import logging
import os
import time


from .compat import json, s as str_from_bytes
from .utils import urlsafe_base64_decode
from .config import UC_HOST, is_customized_default, get_default
from .http.endpoint import Endpoint as _HTTPEndpoint
from .http.regions_provider import Region as _HTTPRegion, ServiceName, get_default_regions_provider


def _legacy_default_get(key):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, key) and getattr(self, key):
                return getattr(self, key)
            if is_customized_default('default_' + key):
                return get_default('default_' + key)
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class LegacyRegion(_HTTPRegion, object):
    """七牛上传区域类
    该类主要内容上传区域地址。
    """

    def __init__(
        self,
        up_host=None,
        up_host_backup=None,
        io_host=None,
        host_cache=None,
        home_dir=None,
        scheme="http",
        rs_host=None,
        rsf_host=None,
        api_host=None,
        accelerate_uploading=False
    ):
        """初始化Zone类"""
        super(LegacyRegion, self).__init__()
        if host_cache is None:
            host_cache = {}
        self.up_host = up_host
        self.up_host_backup = up_host_backup
        self.io_host = io_host
        self.rs_host = rs_host
        self.rsf_host = rsf_host
        self.api_host = api_host
        self.home_dir = home_dir
        self.host_cache = host_cache
        self.scheme = scheme
        self.services.update({
            k: [
                _HTTPEndpoint.from_host(h)
                for h in v if h
            ]
            for k, v in {
                ServiceName.UP: [up_host, up_host_backup],
                ServiceName.IO: [io_host],
                ServiceName.RS: [rs_host],
                ServiceName.RSF: [rsf_host],
                ServiceName.API: [api_host]
            }.items()
        })
        self.accelerate_uploading = accelerate_uploading

    def get_up_host_by_token(self, up_token, home_dir):
        ak, bucket = self.unmarshal_up_token(up_token)
        if home_dir is None:
            home_dir = os.getcwd()
        up_hosts = self.get_up_host(ak, bucket, home_dir)
        return up_hosts[0]

    def get_up_host_backup_by_token(self, up_token, home_dir):
        ak, bucket = self.unmarshal_up_token(up_token)
        if home_dir is None:
            home_dir = os.getcwd()
        up_hosts = self.get_up_host(ak, bucket, home_dir)
        if len(up_hosts) <= 1:
            up_host = up_hosts[0]
        else:
            up_host = up_hosts[1]
        return up_host

    def get_io_host(self, ak, bucket, home_dir=None):
        if self.io_host:
            return self.io_host
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'ioHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        io_hosts = bucket_hosts['ioHosts']
        return io_hosts[0]

    @_legacy_default_get('rs_host')
    def get_rs_host(self, ak, bucket, home_dir=None):
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'rsHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        rs_hosts = bucket_hosts['rsHosts']
        return rs_hosts[0]

    @_legacy_default_get('rsf_host')
    def get_rsf_host(self, ak, bucket, home_dir=None):
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'rsfHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        rsf_hosts = bucket_hosts['rsfHosts']
        return rsf_hosts[0]

    @_legacy_default_get('api_host')
    def get_api_host(self, ak, bucket, home_dir=None):
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'apiHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        api_hosts = bucket_hosts['apiHosts']
        return api_hosts[0]

    def get_up_host(self, ak, bucket, home_dir):
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'upHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        up_hosts = bucket_hosts['upHosts']
        return up_hosts

    def unmarshal_up_token(self, up_token):
        token = up_token.split(':')
        if len(token) != 3:
            raise ValueError('invalid up_token')

        ak = token[0]
        policy = json.loads(
            str_from_bytes(
                urlsafe_base64_decode(
                    token[2])))

        scope = policy["scope"]
        bucket = scope
        if ':' in scope:
            bucket = scope.split(':')[0]

        return ak, bucket

    def get_bucket_hosts(self, ak, bucket, home_dir=None, force=False):
        cache_persist_path = os.path.join(home_dir, 'qn-regions-cache.jsonl') if home_dir else None
        regions = self.__get_bucket_regions(
            ak,
            bucket,
            force_query=force,
            cache_persist_path=cache_persist_path
        )

        if not regions:
            raise KeyError("Please check your BUCKET_NAME! Server hosts not correct! The hosts is empty")

        region = regions[0]

        bucket_hosts = {
            k: [
                e.get_value(scheme=self.scheme)
                for e in region.services[sn]
                if e
            ]
            for k, sn in {
                'upHosts': ServiceName.UP,
                'ioHosts': ServiceName.IO,
                'rsHosts': ServiceName.RS,
                'rsfHosts': ServiceName.RSF,
                'apiHosts': ServiceName.API
            }.items()
        }

        ttl = region.ttl if region.ttl > 0 else 24 * 3600  # 1 day
        # use datetime.datetime.timestamp() when min version of python >= 3
        create_time = int(float(region.create_time.strftime('%s.%f')) * 1000)
        bucket_hosts['deadline'] = create_time + ttl

        return bucket_hosts

    def get_bucket_hosts_to_cache(self, key, home_dir):
        """
        .. deprecated::
            The cache has been replaced by CachedRegionsProvider

        Parameters
        ----------
        key: str
        home_dir: str

        Returns
        -------
        dict
        """
        ret = {}
        if len(self.host_cache) == 0:
            self.host_cache_from_file(home_dir)

        if key not in self.host_cache:
            return ret

        if self.host_cache[key]['deadline'] > time.time():
            ret = self.host_cache[key]

        return ret

    def set_bucket_hosts_to_cache(self, key, val, home_dir):
        """
        .. deprecated::
            The cache has been replaced by CachedRegionsProvider

        Parameters
        ----------
        key: str
        val: dict
        home_dir: str
        """
        self.host_cache[key] = val
        self.host_cache_to_file(home_dir)
        return

    def host_cache_from_file(self, home_dir):
        """
        .. deprecated::
            The cache has been replaced by CachedRegionsProvider

        Parameters
        ----------
        home_dir: str
        """
        if home_dir is not None:
            self.home_dir = home_dir
        path = self.host_cache_file_path()
        if not os.path.isfile(path):
            return None
        with open(path, 'r') as f:
            try:
                bucket_hosts = json.load(f)
                self.host_cache = bucket_hosts
            except Exception as e:
                logging.error(e)
        f.close()
        return

    def host_cache_file_path(self):
        """
        .. deprecated::
            The cache has been replaced by CachedRegionsProvider

        Returns
        -------
        str
        """
        return os.path.join(self.home_dir, ".qiniu_pythonsdk_hostscache.json")

    def host_cache_to_file(self, home_dir):
        """
        .. deprecated::
            The cache has been replaced by CachedRegionsProvider

        Parameters
        ----------
        home_dir: str

        """
        path = self.host_cache_file_path()
        with open(path, 'w') as f:
            json.dump(self.host_cache, f)
        f.close()

    def bucket_hosts(self, ak, bucket):
        regions = self.__get_bucket_regions(ak, bucket)

        data_dict = {
            'hosts': [
                {
                    k.value if isinstance(k, ServiceName) else k: {
                        'domains': [
                            e.host for e in v
                        ]
                    }
                    for k, v in r.services.items()
                }
                for r in regions
            ]
        }
        for r in data_dict['hosts']:
            if 'up_acc' in r:
                r.setdefault('up', {})
                r['up'].update(acc_domains=r['up_acc'].get('domains', []))
                del r['up_acc']

        data = json.dumps(data_dict)

        return data

    def __get_bucket_regions(
        self,
        access_key,
        bucket_name,
        force_query=False,
        cache_persist_path=None
    ):
        query_region_host = UC_HOST
        if is_customized_default('default_query_region_host'):
            query_region_host = get_default('default_query_region_host')
        query_region_backup_hosts = get_default('default_query_region_backup_hosts')
        query_region_backup_retry_times = get_default('default_backup_hosts_retry_times')

        regions_provider = get_default_regions_provider(
            query_endpoints_provider=[
                _HTTPEndpoint.from_host(h)
                for h in [query_region_host] + query_region_backup_hosts
                if h
            ],
            access_key=access_key,
            bucket_name=bucket_name,
            accelerate_uploading=self.accelerate_uploading,
            force_query=force_query,
            preferred_scheme=self.scheme,
            persist_path=cache_persist_path,
            max_retry_times_per_endpoint=query_region_backup_retry_times
        )

        return list(regions_provider)


Region = LegacyRegion
