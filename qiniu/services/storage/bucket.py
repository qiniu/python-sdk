# -*- coding: utf-8 -*-
from qiniu import config, QiniuMacAuth
from qiniu import http
from qiniu.utils import urlsafe_base64_encode, entry, decode_entry
from qiniu.http.endpoint import Endpoint
from qiniu.http.region import Region, ServiceName
from qiniu.http.regions_provider import get_default_regions_provider

from ._bucket_default_retrier import get_default_retrier


class BucketManager(object):
    """空间管理类

    主要涉及了空间资源管理及批量操作接口的实现，具体的接口规格可以参考：
    https://developer.qiniu.com/kodo/1274/rs

    Attributes:
        auth: 账号管理密钥对，Auth对象
    """

    def __init__(
        self,
        auth,
        zone=None,
        regions=None,
        query_regions_endpoints=None,
        preferred_scheme='http'
    ):
        """
        Parameters
        ----------
        auth: Auth
        zone: LegacyRegion
        regions: list[Region]
        query_regions_endpoints: list[Endpoint]
        preferred_scheme: str, default='http'
        """
        self.auth = auth
        self.mac_auth = QiniuMacAuth(
            auth.get_access_key(),
            auth.get_secret_key(),
            auth.disable_qiniu_timestamp_signature)

        if zone is None:
            self.zone = config.get_default('default_zone')
        else:
            self.zone = zone

        self.regions = regions
        self.query_regions_endpoints = query_regions_endpoints
        self.preferred_scheme = preferred_scheme

    def list(self, bucket, prefix=None, marker=None, limit=None, delimiter=None):
        """前缀查询:

        1. 首次请求 marker = None
        2. 无论 err 值如何，均应该先看 ret.get('items') 是否有内容
        3. 如果后续没有更多数据，err 返回 EOF，marker 返回 None（但不通过该特征来判断是否结束）
        具体规格参考:
        https://developer.qiniu.com/kodo/api/list

        Args:
            bucket:     空间名
            prefix:     列举前缀
            marker:     列举标识符
            limit:      单次列举个数限制
            delimiter:  指定目录分隔符

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
            一个EOF信息。
        """
        options = {
            'bucket': bucket,
        }
        if marker is not None:
            options['marker'] = marker
        if limit is not None:
            options['limit'] = limit
        if prefix is not None:
            options['prefix'] = prefix
        if delimiter is not None:
            options['delimiter'] = delimiter

        ret, info = self.__server_do_with_retrier(
            bucket,
            [ServiceName.RSF],
            '/list',
            data=options,
            method='GET'
        )

        eof = False
        if ret and not ret.get('marker'):
            eof = True

        return ret, eof, info

    def list_domains(self, bucket):
        """获取 Bucket 空间域名
        https://developer.qiniu.com/kodo/3949/get-the-bucket-space-domain

        Args:
            bucket: 空间名

        Returns:
            resBody, respInfo
            resBody 为绑定的域名列表，格式：["example.com"]
        """
        return self.__uc_do_with_retrier('/v2/domains?tbl={0}'.format(bucket))

    def stat(self, bucket, key):
        """获取文件信息:

        获取资源的元信息，但不返回文件内容，具体规格参考：
        https://developer.qiniu.com/kodo/api/1308/stat

        Args:
            bucket: 待获取信息资源所在的空间
            key:    待获取资源的文件名

        Returns:
            一个dict变量，类似：
                {
                    "fsize":        5122935,
                    "hash":         "ljfockr0lOil_bZfyaI2ZY78HWoH",
                    "mimeType":     "application/octet-stream",
                    "putTime":      13603956734587420
                    "type":         0
                }
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/stat/{0}'.format(resource)
        )

    def delete(self, bucket, key):
        """删除文件:

        删除指定资源，具体规格参考：
        https://developer.qiniu.com/kodo/api/delete

        Args:
            bucket: 待获取信息资源所在的空间
            key:    待获取资源的文件名

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/delete/{0}'.format(resource)
        )

    def rename(self, bucket, key, key_to, force='false'):
        """重命名文件:

        给资源进行重命名，本质为move操作。

        Args:
            bucket: 待操作资源所在空间
            key:    待操作资源文件名
            key_to: 目标资源文件名
            force:  是否强制覆盖

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        return self.move(bucket, key, bucket, key_to, force)

    def move(self, bucket, key, bucket_to, key_to, force='false'):
        """移动文件:

        将资源从一个空间到另一个空间，具体规格参考：
        https://developer.qiniu.com/kodo/api/move

        Args:
            bucket:     待操作资源所在空间
            bucket_to:  目标资源空间名
            key:        待操作资源文件名
            key_to:     目标资源文件名
            force:      是否强制覆盖

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        src = entry(bucket, key)
        dst = entry(bucket_to, key_to)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/move/{src}/{dst}/force/{force}'.format(
                src=src,
                dst=dst,
                force=force
            )
        )

    def copy(self, bucket, key, bucket_to, key_to, force='false'):
        """复制文件:

        将指定资源复制为新命名资源，具体规格参考：
        https://developer.qiniu.com/kodo/api/copy

        Args:
            bucket:     待操作资源所在空间
            bucket_to:  目标资源空间名
            key:        待操作资源文件名
            key_to:     目标资源文件名
            force:      是否强制覆盖

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        src = entry(bucket, key)
        dst = entry(bucket_to, key_to)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/copy/{src}/{dst}/force/{force}'.format(
                src=src,
                dst=dst,
                force=force
            )
        )

    def fetch(self, url, bucket, key=None, hostscache_dir=None):
        """抓取文件:
        从指定URL抓取资源，并将该资源存储到指定空间中，具体规格参考：
        https://developer.qiniu.com/kodo/api/fetch

        Args:
            url:      指定的URL
            bucket:   目标资源空间
            key:      目标资源文件名
            hostscache_dir: deprecated, 此参数不再生效，可修改 get_default_regions_provider 返回对象的属性达成同样功能；
                查询区域缓存文件保存位置

        Returns:
            一个dict变量：
                成功 返回{'fsize': <fsize int>, 'hash': <hash string>, 'key': <key string>, 'mimeType': <mimeType string>}
                失败 返回 None
            一个ResponseInfo对象
        """
        resource = urlsafe_base64_encode(url)
        to = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.IO],
            '/fetch/{0}/to/{1}'.format(resource, to)
        )

    def prefetch(self, bucket, key, hostscache_dir=None):
        """镜像回源预取文件:

        从镜像源站抓取资源到空间中，如果空间中已经存在，则覆盖该资源，具体规格参考
        https://developer.qiniu.com/kodo/api/prefetch

        Args:
            bucket: 待获取资源所在的空间
            key:    代获取资源文件名
            hostscache_dir: deprecated, 此参数不再生效，可修改 get_default_regions_provider 返回对象的属性达成同样功能；
                查询区域缓存文件保存位置

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.IO],
            '/prefetch/{0}'.format(resource)
        )

    def change_mime(self, bucket, key, mime):
        """修改文件mimeType:

        主动修改指定资源的文件类型，具体规格参考：
        https://developer.qiniu.com/kodo/api/chgm

        Args:
            bucket: 待操作资源所在空间
            key:    待操作资源文件名
            mime:   待操作文件目标mimeType
        """
        resource = entry(bucket, key)
        encode_mime = urlsafe_base64_encode(mime)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/chgm/{0}/mime/{1}'.format(resource, encode_mime)
        )

    def change_type(self, bucket, key, storage_type):
        """修改文件的存储类型

        修改文件的存储类型，参考文档：
        https://developer.qiniu.com/kodo/3710/chtype

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            storage_type:   待操作资源存储类型，0为普通存储，1为低频存储，2 为归档存储，3 为深度归档，4 为归档直读存储
        """
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/chtype/{0}/type/{1}'.format(resource, storage_type)
        )

    def restoreAr(self, bucket, key, freezeAfter_days):
        """
        restore_ar 的别名，用于兼容旧版本

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            freezeAfter_days:   解冻有效时长，取值范围 1～7
        """
        return self.restore_ar(
            bucket,
            key,
            freezeAfter_days
        )

    def restore_ar(self, bucket, key, freeze_after_days):
        """
        解冻归档存储、深度归档存储文件

        对归档存储、深度归档存储文件，进行解冻操作参考文档：
        https://developer.qiniu.com/kodo/6380/restore-archive

        Parameters
        ----------
        bucket: str
        key: str
        freeze_after_days: int

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """

        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/restoreAr/{0}/freezeAfterDays/{1}'.format(resource, freeze_after_days)
        )

    def change_status(self, bucket, key, status, cond):
        """修改文件的状态

        修改文件的存储类型为可用或禁用：

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            status:   待操作资源存储类型，0为启用，1为禁用
        """
        resource = entry(bucket, key)
        url_resource = '/chstatus/{0}/status/{1}'.format(resource, status)
        if cond and isinstance(cond, dict):
            condstr = urlsafe_base64_encode(
                '&'.join(
                    '='.join([k, v])
                    for k, v in cond.items()
                )
            )
            url_resource += '/cond/{0}'.format(condstr)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            url_resource
        )

    def set_object_lifecycle(
        self,
        bucket,
        key,
        to_line_after_days=0,
        to_archive_after_days=0,
        to_deep_archive_after_days=0,
        delete_after_days=0,
        cond=None,
        to_archive_ir_after_days=0
    ):
        """

        设置对象的生命周期

        Args:
            bucket: 目标空间
            key: 目标资源
            to_line_after_days: 多少天后将文件转为低频存储，设置为 -1 表示取消已设置的转低频存储的生命周期规则， 0 表示不修改转低频生命周期规则。
            to_archive_after_days: 多少天后将文件转为归档存储，设置为 -1 表示取消已设置的转归档存储的生命周期规则， 0 表示不修改转归档生命周期规则。
            to_deep_archive_after_days: 多少天后将文件转为深度归档存储，设置为 -1 表示取消已设置的转深度归档存储的生命周期规则， 0 表示不修改转深度归档生命周期规则
            delete_after_days: 多少天后将文件删除，设置为 -1 表示取消已设置的删除存储的生命周期规则， 0 表示不修改删除存储的生命周期规则。
            cond: 匹配条件，只有条件匹配才会设置成功，当前支持设置 hash、mime、fsize、putTime。
            to_archive_ir_after_days: 多少天后将文件转为归档直读存储，设置为 -1 表示取消已设置的转归档只读存储的生命周期规则， 0 表示不修改转归档只读存储生命周期规则。

        Returns:
            resBody, respInfo

        """
        options = [
            'toIAAfterDays', str(to_line_after_days),
            'toArchiveIRAfterDays', str(to_archive_ir_after_days),
            'toArchiveAfterDays', str(to_archive_after_days),
            'toDeepArchiveAfterDays', str(to_deep_archive_after_days),
            'deleteAfterDays', str(delete_after_days)
        ]
        if cond and isinstance(cond, dict):
            cond_str = '&'.join(
                '='.join([k, v])
                for k, v in cond.items()
            )
            options += ['cond', urlsafe_base64_encode(cond_str)]
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            service_names=[ServiceName.RS],
            url_resource='/lifecycle/{0}/{1}'.format(resource, '/'.join(options)),
        )

    def batch(self, operations):
        """批量操作:

        在单次请求中进行多个资源管理操作，具体规格参考：
        https://developer.qiniu.com/kodo/api/batch

        Args:
            operations: 资源管理操作数组，可通过

        Returns:
            一个dict变量，返回结果类似：
                [
                    { "code": <HttpCode int>, "data": <Data> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int>, "data": { "error": "<ErrorMessage string>" } },
                    ...
                ]
            一个ResponseInfo对象
        """
        if not operations:
            # change to ValueError when make break changes version
            raise Exception('operations is empty')
        bucket = ''
        for op in operations:
            segments = op.split('/')
            e = segments[1] if len(segments) >= 2 else ''
            bucket, _ = decode_entry(e)
            if bucket:
                break
        if not bucket:
            # change to ValueError when make break changes version
            raise Exception('bucket is empty')

        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/batch',
            {'op': operations}
        )

    def buckets(self):
        """获取所有空间名:

        获取指定账号下所有的空间名。

        Returns:
            一个dict变量，类似：
                [ <Bucket1>, <Bucket2>, ... ]
            一个ResponseInfo对象
        """
        return self.__uc_do_with_retrier('/buckets')

    def delete_after_days(self, bucket, key, days):
        """更新文件生命周期

        Returns:
            一个dict变量，返回结果类似：
                [
                    { "code": <HttpCode int>, "data": <Data> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int> },
                    { "code": <HttpCode int>, "data": { "error": "<ErrorMessage string>" } },
                    ...
                ]
            一个ResponseInfo对象
        Args:
            bucket: 目标资源空间
            key:    目标资源文件名
            days:   指定天数
        """
        resource = entry(bucket, key)
        return self.__server_do_with_retrier(
            bucket,
            [ServiceName.RS],
            '/deleteAfterDays/{0}/{1}'.format(resource, days)
        )

    def mkbucketv3(self, bucket_name, region):
        """
        创建存储空间，全局唯一，其他账号有同名空间就无法创建

        Args:
            bucket_name: 存储空间名
            region: 存储区域
        """
        return self.__uc_do_with_retrier(
            '/mkbucketv3/{0}/region/{1}'.format(bucket_name, region)
        )

    def list_bucket(self, region):
        """
        列举存储空间列表

        Args:
        """
        return self.__uc_do_with_retrier('/v3/buckets?region={0}'.format(region))

    def bucket_info(self, bucket_name):
        """
        获取存储空间信息

        Args:
            bucket_name: 存储空间名
        """
        return self.__uc_do_with_retrier('/v2/bucketInfo?bucket={0}'.format(bucket_name))

    def bucket_domain(self, bucket_name):
        """
        获取存储空间域名列表
        Args:
            bucket_name: 存储空间名
        """
        return self.list_domains(bucket_name)

    def change_bucket_permission(self, bucket_name, private):
        """
        设置 存储空间访问权限
        https://developer.qiniu.com/kodo/api/3946/set-bucket-private
        Args:
            bucket_name: 存储空间名
            private: 0 公开；1 私有 ,str类型
        """
        return self.__uc_do_with_retrier(
            '/private?bucket={0}&private={1}'.format(bucket_name, private)
        )

    def _get_regions_provider(self, bucket_name):
        """
        Parameters
        ----------
        bucket_name: str

        Returns
        -------
        Iterable[Region]
        """
        if self.regions:
            return self.regions

        # handle compatibility for legacy config
        if self.zone and any(
            hasattr(self.zone, attr_name) and getattr(self.zone, attr_name)
            for attr_name in [
                'io_host',
                'rs_host',
                'rsf_host',
                'api_host'
            ]
        ):
            return [self.zone]

        # handle compatibility for default_query_region_host
        query_regions_endpoints = self.query_regions_endpoints
        if not query_regions_endpoints:
            query_region_host = config.get_default('default_query_region_host')
            query_region_backup_hosts = config.get_default('default_query_region_backup_hosts')
            query_regions_endpoints = [
                Endpoint.from_host(h)
                for h in [query_region_host] + query_region_backup_hosts
            ]

        return get_default_regions_provider(
            query_endpoints_provider=query_regions_endpoints,
            access_key=self.auth.get_access_key(),
            bucket_name=bucket_name,
            preferred_scheme=self.preferred_scheme
        )

    def __uc_do_with_retrier(self, url_resource, data=None):
        """
        Parameters
        ----------
        url_resource: url
        data: dict or None

        Returns
        -------
        ret: dict or None
        resp: ResponseInfo
        """
        regions = self.regions

        # ignore self.zone by no uc in it
        # handle compatibility for default_uc
        if not regions:
            uc_host = config.get_default('default_uc_host')
            uc_endpoints = [
                Endpoint.from_host(h)
                for h in [uc_host]
            ]
            regions = [Region(services={ServiceName.UC: uc_endpoints})]

        retrier = get_default_retrier(
            regions_provider=regions,
            service_names=[ServiceName.UC]
        )

        attempt = None
        for attempt in retrier:
            with attempt:
                host = attempt.context.get('endpoint').get_value(scheme=self.preferred_scheme)
                url = host + url_resource
                attempt.result = self.__post(url, data)
                ret, resp = attempt.result
                if resp.ok() and ret:
                    return attempt.result
                if not resp.need_retry():
                    return attempt.result

        if attempt is None:
            raise RuntimeError('Retrier is not working. attempt is None')

        return attempt.result

    def __server_do_with_retrier(self, bucket_name, service_names, url_resource, data=None, method='POST'):
        """
        Parameters
        ----------
        bucket_name: str
        service_names: List[ServiceName]
        url_resource: str
        data: dict or None
        method: str

        Returns
        -------
        ret: dict or None
        resp: ResponseInfo
        """
        if not service_names:
            raise ValueError('service_names is empty')

        retrier = get_default_retrier(
            regions_provider=self._get_regions_provider(bucket_name=bucket_name),
            service_names=service_names
        )

        method = method.upper()
        if method == 'POST':
            send_request = self.__post
        elif method == 'GET':
            send_request = self.__get
        else:
            raise ValueError('"method" must be "POST" or "GET"')

        attempt = None
        for attempt in retrier:
            with attempt:
                host = attempt.context.get('endpoint').get_value(scheme=self.preferred_scheme)
                url = host + url_resource
                attempt.result = send_request(url, data)
                ret, resp = attempt.result
                if resp.ok() and ret:
                    return attempt.result
                if not resp.need_retry():
                    return attempt.result

        if attempt is None:
            raise RuntimeError('Retrier is not working. attempt is None')

        return attempt.result

    def __post(self, url, data=None):
        return http._post_with_qiniu_mac(url, data, self.mac_auth)

    def __get(self, url, params=None):
        return http._get_with_qiniu_mac(url, params, self.mac_auth)


def _build_op(*args):
    return '/'.join(map(str, args))


def build_batch_copy(source_bucket, key_pairs, target_bucket, force='false'):
    """
    Parameters
    ----------
    source_bucket: str
    key_pairs: dict
    target_bucket: str
    force: str

    Returns
    -------
    list[str]
    """
    return _two_key_batch('copy', source_bucket, key_pairs, target_bucket, force)


def build_batch_rename(bucket, key_pairs, force='false'):
    """
    Parameters
    ----------
    bucket: str
    key_pairs: dict
    force: str

    Returns
    -------
    list[str]
    """
    return build_batch_move(bucket, key_pairs, bucket, force)


def build_batch_move(source_bucket, key_pairs, target_bucket, force='false'):
    """
    Parameters
    ----------
    source_bucket: str
    key_pairs: dict
    target_bucket: str
    force: str

    Returns
    -------
    list[str]
    """
    return _two_key_batch('move', source_bucket, key_pairs, target_bucket, force)


def build_batch_restoreAr(bucket, keys):
    """
    alias for build_batch_restore_ar for compatibility with old version

    Parameters
    ----------
    bucket: str
    keys: dict

    Returns
    -------
    list[str]
    """
    return build_batch_restore_ar(bucket, keys)


def build_batch_restore_ar(bucket, keys):
    """
    Parameters
    ----------
    bucket: str
    keys: dict

    Returns
    -------
    list[str]
    """
    keys = {
        k: ['freezeAfterDays', v]
        for k, v in keys.items()
    }
    return _one_key_batch('restoreAr', bucket, keys)


def build_batch_delete(bucket, keys):
    """
    Parameters
    ----------
    bucket: str
    keys: list[str]

    Returns
    -------
    list[str]
    """
    return _one_key_batch('delete', bucket, keys)


def build_batch_stat(bucket, keys):
    """
    Parameters
    ----------
    bucket: str
    keys: list[str]

    Returns
    -------
    list[str]
    """
    return _one_key_batch('stat', bucket, keys)


def _one_key_batch(operation, bucket, keys):
    """
    Parameters
    ----------
    operation: str
    bucket: str
    keys: list[str] or dict

    Returns
    -------
    list[str]
    """
    # use functools.singledispatch to refactor when min version of python >= 3.4
    if isinstance(keys, list):
        return [
            _build_op(
                operation,
                entry(bucket, key),
            )
            for key in keys
        ]
    elif isinstance(keys, dict):
        return [
            _build_op(
                operation,
                entry(bucket, key),
                *opts
            )
            for key, opts in keys.items()
        ]
    else:
        raise TypeError('"keys" only support list or dict')


def _two_key_batch(operation, source_bucket, key_pairs, target_bucket=None, force='false'):
    """

    Parameters
    ----------
    operation: str
    source_bucket: str
    key_pairs: dict
    target_bucket: str
    force: str

    Returns
    -------
    list[str]
    """
    if target_bucket is None:
        target_bucket = source_bucket
    return _one_key_batch(
        operation,
        source_bucket,
        {
            src_key: [
                entry(target_bucket, dst_key),
                'force',
                force
            ]
            for src_key, dst_key in key_pairs.items()
        }
    )


def _three_key_batch(operation, bucket, keys):
    """
    .. deprecated: Use `_one_key_batch` instead.
        `keys` could be `{key: [freezeAfterDays, days]}`

    Parameters
    ----------
    operation: str
    bucket: str
    keys: dict

    Returns
    -------
    list[str]
    """
    keys = {
        k: ['freezeAfterDays', v]
        for k, v in keys.items()
    }
    return _one_key_batch(operation, bucket, keys)
