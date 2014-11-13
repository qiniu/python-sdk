# -*- coding: utf-8 -*-
# flake8: noqa
import os
import string
import random
import tempfile

import unittest
import pytest

from qiniu import Auth, set_default, etag, PersistentFop, build_op, op_save
from qiniu import put_data, put_file, put_stream
from qiniu import BucketManager, build_batch_copy, build_batch_rename, build_batch_move, build_batch_stat, build_batch_delete
from qiniu import urlsafe_base64_encode, urlsafe_base64_decode

from qiniu.compat import is_py2, b

from qiniu.services.storage.uploader import _form_put

import qiniu.config

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')

dummy_access_key = 'abcdefghklmnopq'
dummy_secret_key = '1234567890'
dummy_auth = Auth(dummy_access_key, dummy_secret_key)


def rand_string(length):
    lib = string.ascii_uppercase
    return ''.join([random.choice(lib) for i in range(0, length)])


def create_temp_file(size):
    t = tempfile.mktemp()
    f = open(t, 'wb')
    f.seek(size-1)
    f.write(b('0'))
    f.close()
    return t


def remove_temp_file(file):
    try:
        os.remove(file)
    except OSError:
        pass


class UtilsTest(unittest.TestCase):

    def test_urlsafe(self):
        a = '你好\x96'
        u = urlsafe_base64_encode(a)
        assert b(a) == urlsafe_base64_decode(u)


class AuthTestCase(unittest.TestCase):

    def test_token(self):
        token = dummy_auth.token('test')
        assert token == 'abcdefghklmnopq:mSNBTR7uS2crJsyFr2Amwv1LaYg='

    def test_token_with_data(self):
        token = dummy_auth.token_with_data('test')
        assert token == 'abcdefghklmnopq:-jP8eEV9v48MkYiBGs81aDxl60E=:dGVzdA=='

    def test_noKey(self):
        with pytest.raises(ValueError):
            Auth(None, None).token('nokey')
        with pytest.raises(ValueError):
            Auth('', '').token('nokey')

    def test_token_of_request(self):
        token = dummy_auth.token_of_request('http://www.qiniu.com?go=1', 'test', '')
        assert token == 'abcdefghklmnopq:cFyRVoWrE3IugPIMP5YJFTO-O-Y='
        token = dummy_auth.token_of_request('http://www.qiniu.com?go=1', 'test', 'application/x-www-form-urlencoded')
        assert token == 'abcdefghklmnopq:svWRNcacOE-YMsc70nuIYdaa1e4='

    def test_deprecatedPolicy(self):
        with pytest.raises(ValueError):
            dummy_auth.upload_token('1', None, policy={'asyncOps': 1})


class BucketTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)
    bucket = BucketManager(q)

    def test_list(self):
        ret, eof, _ = self.bucket.list(bucket_name, limit=4)
        assert eof is False
        assert len(ret.get('items')) == 4
        ret, eof, _ = self.bucket.list(bucket_name, limit=100)
        assert eof is True

    def test_buckets(self):
        ret, _ = self.bucket.buckets()
        assert bucket_name in ret

    def test_pefetch(self):
        ret, _ = self.bucket.prefetch(bucket_name, 'python-sdk.html')
        assert ret == {}

    def test_fetch(self):
        ret, _ = self.bucket.fetch('http://developer.qiniu.com/docs/v6/sdk/python-sdk.html', bucket_name, 'fetch.html')
        assert ret == {}

    def test_stat(self):
        ret, _ = self.bucket.stat(bucket_name, 'python-sdk.html')
        assert 'hash' in ret

    def test_delete(self):
        ret, info = self.bucket.delete(bucket_name, 'del')

    def test_rename(self):
        key = 'renameto'+rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key + 'move'
        ret, _ = self.bucket.rename(bucket_name, key, key2)
        assert ret == {}
        ret, _ = self.bucket.delete(bucket_name, key2)
        assert ret == {}

    def test_copy(self):
        key = 'copyto'+rand_string(8)
        ret, _ = self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)

        assert ret == {}
        ret, _ = self.bucket.delete(bucket_name, key)
        assert ret == {}

    def test_batch_copy(self):
        key = 'copyto'+rand_string(8)
        ops = build_batch_copy(bucket_name, {'copyfrom': key}, bucket_name)
        ret, _ = self.bucket.batch(ops)
        assert ret[0]['code'] == 200
        ops = build_batch_delete(bucket_name, [key])
        ret, _ = self.bucket.batch(ops)
        assert ret[0]['code'] == 200

    def test_batch_move(self):
        key = 'moveto'+rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key2 = key + 'move'
        ops = build_batch_move(bucket_name, {key: key2}, bucket_name)
        ret, _ = self.bucket.batch(ops)
        assert ret[0]['code'] == 200
        ret, _ = self.bucket.delete(bucket_name, key2)
        assert ret == {}

    def test_batch_rename(self):
        key = 'rename'+rand_string(8)
        self.bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
        key2 = key2 = key + 'rename'
        ops = build_batch_move(bucket_name, {key: key2}, bucket_name)
        ret, _ = self.bucket.batch(ops)
        assert ret[0]['code'] == 200
        ret, _ = self.bucket.delete(bucket_name, key2)
        assert ret == {}

    def test_batch_stat(self):
        ops = build_batch_stat(bucket_name, ['python-sdk.html'])
        ret, _ = self.bucket.batch(ops)
        assert ret[0]['code'] == 200


class UploaderTestCase(unittest.TestCase):

    mime_type = "text/plain"
    params = {'x:a': 'a'}
    q = Auth(access_key, secret_key)

    def test_put(self):
        key = 'a\\b\\c"你好'
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        assert ret['key'] == key

        key = ''
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name, key)
        ret, _ = put_data(token, key, data, check_crc=True)
        assert ret['key'] == key

    def test_putfile(self):
        localfile = __file__
        key = 'test_file'

        token = self.q.upload_token(bucket_name, key)
        ret, _ = put_file(token, key, localfile, mime_type=self.mime_type, check_crc=True)
        assert ret['key'] == key
        assert ret['hash'] == etag(localfile)

    def test_putInvalidCrc(self):
        key = 'test_invalid'
        data = 'hello bubby!'
        crc32 = 'wrong crc32'
        token = self.q.upload_token(bucket_name)
        ret, info = _form_put(token, key, data, None, None, crc32=crc32)
        assert ret is None
        assert info.status_code == 400

    def test_putWithoutKey(self):
        key = None
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name)
        ret, _ = put_data(token, key, data)
        assert ret['hash'] == ret['key']

        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name, 'nokey2')

        ret, info = put_data(token, None, data)

    def test_retry(self):
        key = 'retry'
        data = 'hello retry!'
        set_default(default_up_host='a')
        token = self.q.upload_token(bucket_name)
        ret, _ = put_data(token, key, data)
        assert ret['key'] == key
        qiniu.set_default(default_up_host=qiniu.config.UPAUTO_HOST)


class ResumableUploaderTestCase(unittest.TestCase):

    mime_type = "text/plain"
    params = {'x:a': 'a'}
    q = Auth(access_key, secret_key)

    def test_putfile(self):
        localfile = __file__
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, size, self.params, self.mime_type)
            print(info)
            assert ret['key'] == key

    def test_big_file(self):
        key = 'big'
        token = self.q.upload_token(bucket_name, key)
        localfile = create_temp_file(4 * 1024 * 1024 + 1)
        progress_handler = lambda progress, total: progress
        qiniu.set_default(default_up_host='a')
        ret, info = put_file(token, key, localfile, self.params, self.mime_type, progress_handler=progress_handler)
        assert ret['key'] == key
        qiniu.set_default(default_up_host=qiniu.config.UPAUTO_HOST)
        remove_temp_file(localfile)

    def test_retry(self):
        localfile = __file__
        key = 'test_file_r_retry'
        qiniu.set_default(default_up_host='a')
        token = self.q.upload_token(bucket_name, key)
        ret, info = put_file(token, key, localfile, self.params, self.mime_type)
        assert ret['key'] == key
        qiniu.set_default(default_up_host=qiniu.config.UPAUTO_HOST)


class MediaTestCase(unittest.TestCase):
    def test_pfop(self):
        q = Auth(access_key, secret_key)
        pfop = PersistentFop(q, 'testres', 'sdktest')
        op = op_save('avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240', 'pythonsdk', 'pfoptest')
        ret, info = pfop.execute('sintel_trailer.mp4', op, 1)
        assert ret['persistentId'] is not None

if __name__ == '__main__':
    unittest.main()
