# -*- coding: utf-8 -*-
import logging
import os
import time

from qiniu import compat
from qiniu import utils

UC_HOST = 'https://uc.qbox.me'  # 获取空间信息Host


class Region(object):
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
            api_host=None):
        """初始化Zone类"""
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

    def get_rs_host(self, ak, bucket, home_dir=None):
        from .config import get_default, is_customized_default
        if self.rs_host:
            return self.rs_host
        if is_customized_default('default_rs_host'):
            return get_default('default_rs_host')
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'rsHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        rs_hosts = bucket_hosts['rsHosts']
        return rs_hosts[0]

    def get_rsf_host(self, ak, bucket, home_dir=None):
        from .config import get_default, is_customized_default
        if self.rsf_host:
            return self.rsf_host
        if is_customized_default('default_rsf_host'):
            return get_default('default_rsf_host')
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'rsfHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        rsf_hosts = bucket_hosts['rsfHosts']
        return rsf_hosts[0]

    def get_api_host(self, ak, bucket, home_dir=None):
        from .config import get_default, is_customized_default
        if self.api_host:
            return self.api_host
        if is_customized_default('default_api_host'):
            return get_default('default_api_host')
        if home_dir is None:
            home_dir = os.getcwd()
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'apiHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        api_hosts = bucket_hosts['apiHosts']
        return api_hosts[0]

    def get_up_host(self, ak, bucket, home_dir):
        bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir)
        if 'upHosts' not in bucket_hosts:
            bucket_hosts = self.get_bucket_hosts(ak, bucket, home_dir, force=True)
        up_hosts = bucket_hosts['upHosts']
        return up_hosts

    def unmarshal_up_token(self, up_token):
        token = up_token.split(':')
        if (len(token) != 3):
            raise ValueError('invalid up_token')

        ak = token[0]
        policy = compat.json.loads(
            compat.s(
                utils.urlsafe_base64_decode(
                    token[2])))

        scope = policy["scope"]
        bucket = scope
        if (':' in scope):
            bucket = scope.split(':')[0]

        return ak, bucket

    def get_bucket_hosts(self, ak, bucket, home_dir, force=False):
        key = self.scheme + ":" + ak + ":" + bucket

        bucket_hosts = self.get_bucket_hosts_to_cache(key, home_dir)
        if not force and len(bucket_hosts) > 0:
            return bucket_hosts

        hosts = compat.json.loads(self.bucket_hosts(ak, bucket)).get('hosts', [])

        if type(hosts) is not list or len(hosts) == 0:
            raise KeyError("Please check your BUCKET_NAME! Server hosts not correct! The hosts is %s" % hosts)

        region = hosts[0]

        default_ttl = 24 * 3600  # 1 day
        region['ttl'] = region.get('ttl', default_ttl)

        bucket_hosts = {
            'upHosts': [
                '{0}://{1}'.format(self.scheme, domain)
                for domain in region.get('up', {}).get('domains', [])
            ],
            'ioHosts': [
                '{0}://{1}'.format(self.scheme, domain)
                for domain in region.get('io', {}).get('domains', [])
            ],
            'rsHosts': [
                '{0}://{1}'.format(self.scheme, domain)
                for domain in region.get('rs', {}).get('domains', [])
            ],
            'rsfHosts': [
                '{0}://{1}'.format(self.scheme, domain)
                for domain in region.get('rsf', {}).get('domains', [])
            ],
            'apiHosts': [
                '{0}://{1}'.format(self.scheme, domain)
                for domain in region.get('api', {}).get('domains', [])
            ],
            'deadline': int(time.time()) + region['ttl']
        }
        home_dir = ""
        self.set_bucket_hosts_to_cache(key, bucket_hosts, home_dir)
        return bucket_hosts

    def get_bucket_hosts_to_cache(self, key, home_dir):
        ret = {}
        if len(self.host_cache) == 0:
            self.host_cache_from_file(home_dir)

        if key not in self.host_cache:
            return ret

        if self.host_cache[key]['deadline'] > time.time():
            ret = self.host_cache[key]

        return ret

    def set_bucket_hosts_to_cache(self, key, val, home_dir):
        self.host_cache[key] = val
        self.host_cache_to_file(home_dir)
        return

    def host_cache_from_file(self, home_dir):
        if home_dir is not None:
            self.home_dir = home_dir
        path = self.host_cache_file_path()
        if not os.path.isfile(path):
            return None
        with open(path, 'r') as f:
            try:
                bucket_hosts = compat.json.load(f)
                self.host_cache = bucket_hosts
            except Exception as e:
                logging.error(e)
        f.close()
        return

    def host_cache_file_path(self):
        return os.path.join(self.home_dir, ".qiniu_pythonsdk_hostscache.json")

    def host_cache_to_file(self, home_dir):
        path = self.host_cache_file_path()
        with open(path, 'w') as f:
            compat.json.dump(self.host_cache, f)
        f.close()

    def bucket_hosts(self, ak, bucket):
        from .config import get_default, is_customized_default
        from .http import qn_http_client
        from .http.middleware import RetryDomainsMiddleware
        uc_host = UC_HOST
        if is_customized_default('default_uc_host'):
            uc_host = get_default('default_uc_host')
        uc_backup_hosts = get_default('default_uc_backup_hosts')
        uc_backup_retry_times = get_default('default_uc_backup_retry_times')
        url = "{0}/v4/query?ak={1}&bucket={2}".format(uc_host, ak, bucket)

        def retry_condition(resp, _):
            if resp is None:
                return True
            if resp.status_code in [612, 631]:
                # 612 is app / accesskey is not found
                # 631 is no such bucket
                return False
            return not resp.ok

        ret, _resp = qn_http_client.get(
            url,
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=uc_backup_hosts,
                    max_retry_times=uc_backup_retry_times,
                    retry_condition=retry_condition
                )
            ]
        )
        data = compat.json.dumps(ret, separators=(',', ':'))
        return data
