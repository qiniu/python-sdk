# -*- coding: utf-8 -*-

from qiniu import config
from qiniu.utils import urlsafe_base64_encode, entry
from qiniu import http


class BucketManager(object):

    def __init__(self, auth):
        self.auth = auth

    def list(self, bucket, prefix=None, marker=None, limit=None, delimiter=None):
        """前缀查询:
         * bucket => str
         * prefix => str
         * marker => str
         * limit => int
         * delimiter => str
         * return ret => {'items': items, 'marker': markerOut}, err => str

        1. 首次请求 marker = None
        2. 无论 err 值如何，均应该先看 ret.get('items') 是否有内容
        3. 如果后续没有更多数据，err 返回 EOF，markerOut 返回 None（但不通过该特征来判断是否结束）
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
        resource = entry(bucket, key)
        return self.__rs_do('stat', resource)

    def delete(self, bucket, key):
        resource = entry(bucket, key)
        return self.__rs_do('delete', resource)

    def rename(self, bucket, key, key_to):
        return self.move(bucket, key, bucket, key_to)

    def move(self, bucket, key, bucket_to, key_to):
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do('move', resource, to)

    def copy(self, bucket, key, bucket_to, key_to):
        resource = entry(bucket, key)
        to = entry(bucket_to, key_to)
        return self.__rs_do('copy', resource, to)

    def fetch(self, url, bucket, key):
        resource = urlsafe_base64_encode(url)
        to = entry(bucket, key)
        return self.__io_do('fetch', resource, 'to/{0}'.format(to))

    def prefetch(self, bucket, key):
        resource = entry(bucket, key)
        return self.__io_do('prefetch', resource)

    def change_mime(self, bucket, key, mime):
        resource = entry(bucket, key)
        encode_mime = urlsafe_base64_encode(mime)
        return self.__rs_do('chgm', resource, 'mime/{0}'.format(encode_mime))

    def batch(self, operations):
        url = 'http://{0}/batch'.format(config.RS_HOST)
        return self.__post(url, dict(op=operations))

    def buckets(self):
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
