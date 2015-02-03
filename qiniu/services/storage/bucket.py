# -*- coding: utf-8 -*-

from qiniu import config
from qiniu.utils import urlsafe_base64_encode, entry
from qiniu import http


class BucketManager(object):
    """空间管理类

    主要涉及了空间资源管理及批量操作接口的实现，具体的接口规格可以参考：
    http://developer.qiniu.com/docs/v6/api/reference/rs/

    Attributes:
        auth: 账号管理密钥对，Auth对象
    """

    def __init__(self, auth):
        self.auth = auth

    def list(self, bucket, prefix=None, marker=None, limit=None, delimiter=None):
        """前缀查询:

        1. 首次请求 marker = None
        2. 无论 err 值如何，均应该先看 ret.get('items') 是否有内容
        3. 如果后续没有更多数据，err 返回 EOF，marker 返回 None（但不通过该特征来判断是否结束）
        具体规格参考:
        http://developer.qiniu.com/docs/v6/api/reference/rs/list.html

        Args:
            bucket:     空间名
            prefix:     列举前缀
            marker:     列举标识符
            limit:      单次列举个数限制
            delimiter:  指定目录分隔符

        Returns:
            一个json串，内容详见list接口返回的items。
            一个包含响应头部信息的字符串。
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

        url = 'http://{0}/list'.format(config.RSF_HOST)
        ret, info = self.__get(url, options)

        eof = False
        if ret and not ret.get('marker'):
            eof = True

        return ret, eof, info

    def stat(self, bucket, key):
        """获取文件信息"""
        resource = entry(bucket, key)
        return self.__rs_do('stat', resource)

    def delete(self, bucket, key):
        """删除文件"""
        resource = entry(bucket, key)
        return self.__rs_do('delete', resource)

    def rename(self, bucket, key, key_to):
        """重命名文件"""
        return self.move(bucket, key, bucket, key_to)

    def move(self, bucket, key, bucket_to, key_to):
        """移动文件"""
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do('move', resource, to)

    def copy(self, bucket, key, bucket_to, key_to):
        """复制文件"""
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do('copy', resource, to)

    def fetch(self, url, bucket, key):
        """抓取文件"""
        resource = urlsafe_base64_encode(url)
        to = entry(bucket, key)
        return self.__io_do('fetch', resource, 'to/{0}'.format(to))

    def prefetch(self, bucket, key):
        """镜像回源预取文件"""
        resource = entry(bucket, key)
        return self.__io_do('prefetch', resource)

    def change_mime(self, bucket, key, mime):
        """修改文件mimeType"""
        resource = entry(bucket, key)
        encode_mime = urlsafe_base64_encode(mime)
        return self.__rs_do('chgm', resource, 'mime/{0}'.format(encode_mime))

    def batch(self, operations):
        """批量操作"""
        url = 'http://{0}/batch'.format(config.RS_HOST)
        return self.__post(url, dict(op=operations))

    def buckets(self):
        """获取所有空间名"""
        return self.__rs_do('buckets')

    def __rs_do(self, operation, *args):
        return self.__server_do(config.RS_HOST, operation, *args)

    def __io_do(self, operation, *args):
        return self.__server_do(config.IO_HOST, operation, *args)

    def __server_do(self, host, operation, *args):
        cmd = _build_op(operation, *args)
        url = 'http://{0}/{1}'.format(host, cmd)
        return self.__post(url)

    def __post(self, url, data=None):
        return http._post_with_auth(url, data, self.auth)

    def __get(self, url, params=None):
        return http._get(url, params, self.auth)


def _build_op(*args):
    return '/'.join(args)


def build_batch_copy(source_bucket, key_pairs, target_bucket):
    return _two_key_batch('copy', source_bucket, key_pairs, target_bucket)


def build_batch_rename(bucket, key_pairs):
    return build_batch_move(bucket, key_pairs, bucket)


def build_batch_move(source_bucket, key_pairs, target_bucket):
    return _two_key_batch('move', source_bucket, key_pairs, target_bucket)


def build_batch_delete(bucket, keys):
    return _one_key_batch('delete', bucket, keys)


def build_batch_stat(bucket, keys):
    return _one_key_batch('stat', bucket, keys)


def _one_key_batch(operation, bucket, keys):
    return [_build_op(operation, entry(bucket, key)) for key in keys]


def _two_key_batch(operation, source_bucket, key_pairs, target_bucket):
    if target_bucket is None:
        target_bucket = source_bucket
    return [_build_op(operation, entry(source_bucket, k), entry(target_bucket, v)) for k, v in key_pairs.items()]
