# -*- coding: utf-8 -*-

from qiniu import config, QiniuMacAuth
from qiniu import http
from qiniu.utils import urlsafe_base64_encode, entry


class BucketManager(object):
    """空间管理类

    主要涉及了空间资源管理及批量操作接口的实现，具体的接口规格可以参考：
    https://developer.qiniu.com/kodo/1274/rs

    Attributes:
        auth: 账号管理密钥对，Auth对象
    """

    def __init__(self, auth, zone=None):
        self.auth = auth
        self.mac_auth = QiniuMacAuth(
            auth.get_access_key(),
            auth.get_secret_key(),
            auth.disable_qiniu_timestamp_signature)
        if (zone is None):
            self.zone = config.get_default('default_zone')
        else:
            self.zone = zone

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

        ak = self.auth.get_access_key()
        rs_host = self.zone.get_rsf_host(ak, bucket)
        url = '{0}/list'.format(rs_host)
        ret, info = self.__get(url, options)

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
        return self.__uc_do('v2/domains?tbl={0}'.format(bucket))

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
        return self.__rs_do(bucket, 'stat', resource)

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
        return self.__rs_do(bucket, 'delete', resource)

    def rename(self, bucket, key, key_to, force='false'):
        """重命名文件:

        给资源进行重命名，本质为move操作。

        Args:
            bucket: 待操作资源所在空间
            key:    待操作资源文件名
            key_to: 目标资源文件名

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

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do(bucket, 'move', resource, to, 'force/{0}'.format(force))

    def copy(self, bucket, key, bucket_to, key_to, force='false'):
        """复制文件:

        将指定资源复制为新命名资源，具体规格参考：
        https://developer.qiniu.com/kodo/api/copy

        Args:
            bucket:     待操作资源所在空间
            bucket_to:  目标资源空间名
            key:        待操作资源文件名
            key_to:     目标资源文件名

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do(bucket, 'copy', resource, to, 'force/{0}'.format(force))

    def fetch(self, url, bucket, key=None, hostscache_dir=None):
        """抓取文件:
        从指定URL抓取资源，并将该资源存储到指定空间中，具体规格参考：
        https://developer.qiniu.com/kodo/api/fetch

        Args:
            url:      指定的URL
            bucket:   目标资源空间
            key:      目标资源文件名
            hostscache_dir： host请求 缓存文件保存位置

        Returns:
            一个dict变量：
                成功 返回{'fsize': <fsize int>, 'hash': <hash string>, 'key': <key string>, 'mimeType': <mimeType string>}
                失败 返回 None
            一个ResponseInfo对象
        """
        resource = urlsafe_base64_encode(url)
        to = entry(bucket, key)
        return self.__io_do(bucket, 'fetch', hostscache_dir, resource, 'to/{0}'.format(to))

    def prefetch(self, bucket, key, hostscache_dir=None):
        """镜像回源预取文件:

        从镜像源站抓取资源到空间中，如果空间中已经存在，则覆盖该资源，具体规格参考
        https://developer.qiniu.com/kodo/api/prefetch

        Args:
            bucket: 待获取资源所在的空间
            key:    代获取资源文件名
            hostscache_dir： host请求 缓存文件保存位置

        Returns:
            一个dict变量，成功返回NULL，失败返回{"error": "<errMsg string>"}
            一个ResponseInfo对象
        """
        resource = entry(bucket, key)
        return self.__io_do(bucket, 'prefetch', hostscache_dir, resource)

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
        return self.__rs_do(bucket, 'chgm', resource, 'mime/{0}'.format(encode_mime))

    def change_type(self, bucket, key, storage_type):
        """修改文件的存储类型

        修改文件的存储类型，参考文档：
        https://developer.qiniu.com/kodo/3710/chtype

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            storage_type:   待操作资源存储类型，0为普通存储，1为低频存储，2 为归档存储，3 为深度归档
        """
        resource = entry(bucket, key)
        return self.__rs_do(bucket, 'chtype', resource, 'type/{0}'.format(storage_type))

    def restoreAr(self, bucket, key, freezeAfter_days):
        """解冻归档存储、深度归档存储文件

        对归档存储、深度归档存储文件，进行解冻操作参考文档：
        https://developer.qiniu.com/kodo/6380/restore-archive

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            freezeAfter_days:   解冻有效时长，取值范围 1～7
        """
        resource = entry(bucket, key)
        return self.__rs_do(bucket, 'restoreAr', resource, 'freezeAfterDays/{0}'.format(freezeAfter_days))

    def change_status(self, bucket, key, status, cond):
        """修改文件的状态

        修改文件的存储类型为可用或禁用：

        Args:
            bucket:         待操作资源所在空间
            key:            待操作资源文件名
            storage_type:   待操作资源存储类型，0为启用，1为禁用
        """
        resource = entry(bucket, key)
        if cond and isinstance(cond, dict):
            condstr = ""
            for k, v in cond.items():
                condstr += "{0}={1}&".format(k, v)
            condstr = urlsafe_base64_encode(condstr[:-1])
            return self.__rs_do(bucket, 'chstatus', resource, 'status/{0}'.format(status), 'cond', condstr)
        return self.__rs_do(bucket, 'chstatus', resource, 'status/{0}'.format(status))

    def set_object_lifecycle(
        self,
        bucket,
        key,
        to_line_after_days=0,
        to_archive_after_days=0,
        to_deep_archive_after_days=0,
        delete_after_days=0,
        cond=None
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

        Returns:
            resBody, respInfo

        """
        options = [
            'toIAAfterDays', str(to_line_after_days),
            'toArchiveAfterDays', str(to_archive_after_days),
            'toDeepArchiveAfterDays', str(to_deep_archive_after_days),
            'deleteAfterDays', str(delete_after_days)
        ]
        if cond and isinstance(cond, dict):
            cond_str = '&'.join(["{0}={1}".format(k, v) for k, v in cond.items()])
            options += ['cond', urlsafe_base64_encode(cond_str)]
        resource = entry(bucket, key)
        return self.__rs_do(bucket, 'lifecycle', resource, *options)

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
        url = '{0}/batch'.format(config.get_default('default_rs_host'))
        return self.__post(url, dict(op=operations))

    def buckets(self):
        """获取所有空间名:

        获取指定账号下所有的空间名。

        Returns:
            一个dict变量，类似：
                [ <Bucket1>, <Bucket2>, ... ]
            一个ResponseInfo对象
        """
        return self.__uc_do('buckets')

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
        return self.__rs_do(bucket, 'deleteAfterDays', resource, days)

    def mkbucketv3(self, bucket_name, region):
        """
        创建存储空间，全局唯一，其他账号有同名空间就无法创建

        Args:
            bucket_name: 存储空间名
            region: 存储区域
        """
        return self.__uc_do('mkbucketv3', bucket_name, 'region', region)

    def list_bucket(self, region):
        """
        列举存储空间列表

        Args:
        """
        return self.__uc_do('v3/buckets?region={0}'.format(region))

    def bucket_info(self, bucket_name):
        """
        获取存储空间信息

        Args:
            bucket_name: 存储空间名
        """
        return self.__uc_do('v2/bucketInfo?bucket={}'.format(bucket_name), )

    def bucket_domain(self, bucket_name):
        """
        获取存储空间域名列表
        Args:
            bucket_name: 存储空间名
        """
        data = 'tbl={0}'.format(bucket_name)
        return self.__api_do(bucket_name, 'v6/domain/list', data)

    def change_bucket_permission(self, bucket_name, private):
        """
        设置 存储空间访问权限
        https://developer.qiniu.com/kodo/api/3946/set-bucket-private
        Args:
            bucket_name: 存储空间名
            private: 0 公开；1 私有 ,str类型
        """
        url = "{0}/private?bucket={1}&private={2}".format(config.get_default("default_uc_host"), bucket_name, private)
        return self.__post(url)

    def __api_do(self, bucket, operation, data=None):
        ak = self.auth.get_access_key()
        api_host = self.zone.get_api_host(ak, bucket)
        url = '{0}/{1}'.format(api_host, operation)
        return self.__post(url, data)

    def __uc_do(self, operation, *args):
        return self.__server_do(config.get_default('default_uc_host'), operation, *args)

    def __rs_do(self, bucket, operation, *args):
        ak = self.auth.get_access_key()
        rs_host = self.zone.get_rs_host(ak, bucket)
        return self.__server_do(rs_host, operation, *args)

    def __io_do(self, bucket, operation, home_dir, *args):
        ak = self.auth.get_access_key()
        io_host = self.zone.get_io_host(ak, bucket, home_dir)
        return self.__server_do(io_host, operation, *args)

    def __server_do(self, host, operation, *args):
        cmd = _build_op(operation, *args)
        url = '{0}/{1}'.format(host, cmd)
        return self.__post(url)

    def __post(self, url, data=None):
        return http._post_with_qiniu_mac(url, data, self.mac_auth)

    def __get(self, url, params=None):
        return http._get_with_qiniu_mac(url, params, self.mac_auth)


def _build_op(*args):
    return '/'.join(args)


def build_batch_copy(source_bucket, key_pairs, target_bucket, force='false'):
    return _two_key_batch('copy', source_bucket, key_pairs, target_bucket, force)


def build_batch_rename(bucket, key_pairs, force='false'):
    return build_batch_move(bucket, key_pairs, bucket, force)


def build_batch_move(source_bucket, key_pairs, target_bucket, force='false'):
    return _two_key_batch('move', source_bucket, key_pairs, target_bucket, force)


def build_batch_restoreAr(bucket, keys):
    return _three_key_batch('restoreAr', bucket, keys)


def build_batch_delete(bucket, keys):
    return _one_key_batch('delete', bucket, keys)


def build_batch_stat(bucket, keys):
    return _one_key_batch('stat', bucket, keys)


def _one_key_batch(operation, bucket, keys):
    return [_build_op(operation, entry(bucket, key)) for key in keys]


def _two_key_batch(operation, source_bucket, key_pairs, target_bucket, force='false'):
    if target_bucket is None:
        target_bucket = source_bucket
    return [_build_op(operation, entry(source_bucket, k), entry(target_bucket, v), 'force/{0}'.format(force)) for k, v
            in key_pairs.items()]


def _three_key_batch(operation, bucket, keys):
    return [_build_op(operation, entry(bucket, k), 'freezeAfterDays/{0}'.format(v)) for k, v
            in keys.items()]
