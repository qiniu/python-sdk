# -*- coding: utf-8 -*-
# flake8: noqa
import os
import string
import random
import tempfile
import functools

import requests

import unittest
import pytest
from freezegun import freeze_time

from qiniu import Auth, set_default, etag, PersistentFop, build_op, op_save, Zone, QiniuMacAuth
from qiniu import BucketManager, build_batch_copy, build_batch_rename, build_batch_move, build_batch_stat, \
    build_batch_delete, DomainManager
from qiniu import urlsafe_base64_encode, urlsafe_base64_decode, canonical_mime_header_key, entry, decode_entry

from qiniu.compat import is_py2, is_py3, b, json

import qiniu.config


if is_py2:
    import sys
    import StringIO
    import urllib
    from imp import reload

    reload(sys)
    sys.setdefaultencoding('utf-8')
    StringIO = StringIO.StringIO
    urlopen = urllib.urlopen
elif is_py3:
    import io
    import urllib

    StringIO = io.StringIO
    urlopen = urllib.request.urlopen

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')
hostscache_dir = None


def rand_string(length):
    lib = string.ascii_uppercase
    return ''.join([random.choice(lib) for i in range(0, length)])


def create_temp_file(size):
    t = tempfile.mktemp()
    f = open(t, 'wb')
    f.seek(size - 1)
    f.write(b('0'))
    f.close()
    return t


def remove_temp_file(file):
    try:
        os.remove(file)
    except OSError:
        pass

class BucketTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)
    bucket = BucketManager(q)

    def test_list(self):
        ret, eof, info = self.bucket.list(bucket_name, limit=4)
        assert eof is False
        assert len(ret.get('items')) == 4
        ret, eof, info = self.bucket.list(bucket_name, limit=1000)
        assert info.status_code == 200, info

    def test_buckets(self):
        ret, info = self.bucket.buckets()
        print(info)
        assert bucket_name in ret

    def test_prefetch(self):
        ret, info = self.bucket.prefetch(bucket_name, 'python-sdk.html', hostscache_dir=hostscache_dir)
        print(info)
        assert ret['key'] == 'python-sdk.html'

    def test_fetch(self):
        ret, info = self.bucket.fetch('https://developer.qiniu.com/kodo/sdk/python', bucket_name,
                                      'fetch.html', hostscache_dir=hostscache_dir)
        print(info)
        assert ret['key'] == 'fetch.html'
        assert 'hash' in ret

    def test_fetch_without_key(self):
        ret, info = self.bucket.fetch('https://developer.qiniu.com/kodo/sdk/python', bucket_name,
                                      hostscache_dir=hostscache_dir)
        print(info)
        assert ret['key'] == ret['hash']
        assert 'hash' in ret

    def test_stat(self):
        ret, info = self.bucket.stat(bucket_name, 'python-sdk.html')
        print(info)
        assert 'hash' in ret

    def test_delete(self):
        ret, info = self.bucket.delete(bucket_name, 'del')
        print(info)
        assert ret is None
        assert info.status_code == 612

    def test_rename(self):
        key = 'renameto' + rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key + 'move'
        ret, info = self.bucket.rename(bucket_name, key, key2)
        print(info)
        assert ret == {}
        ret, info = self.bucket.delete(bucket_name, key2)
        print(info)
        assert ret == {}

    def test_copy(self):
        key = 'copyto' + rand_string(8)
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        print(info)
        assert ret == {}
        ret, info = self.bucket.delete(bucket_name, key)
        print(info)
        assert ret == {}

    def test_change_mime(self):
        ret, info = self.bucket.change_mime(bucket_name, 'python-sdk.html', 'text/html')
        print(info)
        assert ret == {}

    def test_change_type(self):
        target_key = 'copyto' + rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, target_key)
        ret, info = self.bucket.change_type(bucket_name, target_key, 1)
        print(info)
        assert ret == {}
        ret, info = self.bucket.stat(bucket_name, target_key)
        print(info)
        assert 'type' in ret
        self.bucket.delete(bucket_name, target_key)

    def test_copy_force(self):
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, 'copyfrom', force='true')
        print(info)
        assert info.status_code == 200

    def test_batch_copy(self):
        key = 'copyto' + rand_string(8)
        ops = build_batch_copy(bucket_name, {'copyfrom': key}, bucket_name)
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200
        ops = build_batch_delete(bucket_name, [key])
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200

    def test_batch_copy_force(self):
        ops = build_batch_copy(bucket_name, {'copyfrom': 'copyfrom'}, bucket_name, force='true')
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200

    def test_batch_move(self):
        key = 'moveto' + rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key + 'move'
        ops = build_batch_move(bucket_name, {key: key2}, bucket_name)
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200
        ret, info = self.bucket.delete(bucket_name, key2)
        print(info)
        assert ret == {}

    def test_batch_move_force(self):
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, 'copyfrom', force='true')
        print(info)
        assert info.status_code == 200
        ops = build_batch_move(bucket_name, {'copyfrom': 'copyfrom'}, bucket_name, force='true')
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200

    def test_batch_rename(self):
        key = 'rename' + rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key + 'rename'
        ops = build_batch_move(bucket_name, {key: key2}, bucket_name)
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200
        ret, info = self.bucket.delete(bucket_name, key2)
        print(info)
        assert ret == {}

    def test_batch_rename_force(self):
        ret, info = self.bucket.rename(bucket_name, 'copyfrom', 'copyfrom', force='true')
        print(info)
        assert info.status_code == 200
        ops = build_batch_rename(bucket_name, {'copyfrom': 'copyfrom'}, force='true')
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200

    def test_batch_stat(self):
        ops = build_batch_stat(bucket_name, ['python-sdk.html'])
        ret, info = self.bucket.batch(ops)
        print(info)
        assert ret[0]['code'] == 200

    def test_delete_after_days(self):
        days = '5'
        ret, info = self.bucket.delete_after_days(bucket_name, 'invaild.html', days)
        assert info.status_code == 612
        key = 'copyto' + rand_string(8)
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        ret, info = self.bucket.delete_after_days(bucket_name, key, days)
        assert info.status_code == 200

    def test_set_object_lifecycle(self):
        key = 'test_set_object_lifecycle' + rand_string(8)
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        assert info.status_code == 200
        ret, info = self.bucket.set_object_lifecycle(
            bucket=bucket_name,
            key=key,
            to_line_after_days=10,
            to_archive_ir_after_days=15,
            to_archive_after_days=20,
            to_deep_archive_after_days=30,
            delete_after_days=40
        )
        assert info.status_code == 200

    def test_set_object_lifecycle_with_cond(self):
        key = 'test_set_object_lifecycle_cond' + rand_string(8)
        ret, info = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        assert info.status_code == 200
        ret, info = self.bucket.stat(bucket_name, key)
        assert info.status_code == 200
        key_hash = ret['hash']
        ret, info = self.bucket.set_object_lifecycle(
            bucket=bucket_name,
            key=key,
            to_line_after_days=10,
            to_archive_ir_after_days=15,
            to_archive_after_days=20,
            to_deep_archive_after_days=30,
            delete_after_days=40,
            cond={
                'hash': key_hash
            }
        )
        assert info.status_code == 200

    def test_list_domains(self):
        ret, info = self.bucket.list_domains(bucket_name)
        print(info)
        assert info.status_code == 200
        assert isinstance(ret, list)

    @freeze_time("1970-01-01")
    def test_invalid_x_qiniu_date(self):
        ret, info = self.bucket.stat(bucket_name, 'python-sdk.html')
        assert ret is None
        assert info.status_code == 403

    @freeze_time("1970-01-01")
    def test_invalid_x_qiniu_date_with_disable_date_sign(self):
        q = Auth(access_key, secret_key, disable_qiniu_timestamp_signature=True)
        bucket = BucketManager(q)
        ret, info = bucket.stat(bucket_name, 'python-sdk.html')
        assert 'hash' in ret

    @freeze_time("1970-01-01")
    def test_invalid_x_qiniu_date_env(self):
        os.environ['DISABLE_QINIU_TIMESTAMP_SIGNATURE'] = 'True'
        ret, info = self.bucket.stat(bucket_name, 'python-sdk.html')
        if hasattr(os, 'unsetenv'):
            os.unsetenv('DISABLE_QINIU_TIMESTAMP_SIGNATURE')
        else:
            # fix unsetenv not exists in earlier python on windows
            os.environ['DISABLE_QINIU_TIMESTAMP_SIGNATURE'] = ''
        assert 'hash' in ret

    @freeze_time("1970-01-01")
    def test_invalid_x_qiniu_date_env_be_ignored(self):
        os.environ['DISABLE_QINIU_TIMESTAMP_SIGNATURE'] = 'True'
        q = Auth(access_key, secret_key, disable_qiniu_timestamp_signature=False)
        bucket = BucketManager(q)
        ret, info = bucket.stat(bucket_name, 'python-sdk.html')
        if hasattr(os, 'unsetenv'):
            os.unsetenv('DISABLE_QINIU_TIMESTAMP_SIGNATURE')
        else:
            # fix unsetenv not exists in earlier python on windows
            os.environ['DISABLE_QINIU_TIMESTAMP_SIGNATURE'] = ''
        assert ret is None
        assert info.status_code == 403

class DownloadTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)

    def test_private_url(self):
        private_bucket_domain = 'private-sdk.peterpy.cn'
        private_key = 'gogopher.jpg'
        base_url = 'http://%s/%s' % (private_bucket_domain, private_key)
        private_url = self.q.private_download_url(base_url, expires=3600)
        print(private_url)
        r = requests.get(private_url)
        assert r.status_code == 200


class EtagTestCase(unittest.TestCase):
    def test_zero_size(self):
        open("x", 'a').close()
        hash = etag("x")
        assert hash == 'Fto5o-5ea0sNMlW_75VgGJCv2AcJ'
        remove_temp_file("x")

    def test_small_size(self):
        localfile = create_temp_file(1024 * 1024)
        hash = etag(localfile)
        assert hash == 'FnlAdmDasGTQOIgrU1QIZaGDv_1D'
        remove_temp_file(localfile)

    def test_large_size(self):
        localfile = create_temp_file(4 * 1024 * 1024 + 1)
        hash = etag(localfile)
        assert hash == 'ljF323utglY3GI6AvLgawSJ4_dgk'
        remove_temp_file(localfile)


class CdnTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)
    domain_manager = DomainManager(q)

    def test_get_domain(self):
        ret, info = self.domain_manager.get_domain('pythonsdk.qiniu.io')
        print(info)
        assert info.status_code == 200


class ReadWithoutSeek(object):
    def __init__(self, str):
        self.str = str
        pass

    def read(self):
        print(self.str)


if __name__ == '__main__':
    unittest.main()
