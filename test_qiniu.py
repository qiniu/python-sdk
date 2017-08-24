# -*- coding: utf-8 -*-
# flake8: noqa
import os
import string
import random
import tempfile
import requests

import unittest
import pytest

from qiniu import Auth, set_default, etag, PersistentFop, build_op, op_save, Zone
from qiniu import put_data, put_file, put_stream
from qiniu import BucketManager, build_batch_copy, build_batch_rename, build_batch_move, build_batch_stat, \
    build_batch_delete
from qiniu import urlsafe_base64_encode, urlsafe_base64_decode

from qiniu.compat import is_py2, is_py3, b

from qiniu.services.storage.uploader import _form_put

import qiniu.config

if is_py2:
    import sys
    import StringIO
    import urllib

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

dummy_access_key = 'abcdefghklmnopq'
dummy_secret_key = '1234567890'
dummy_auth = Auth(dummy_access_key, dummy_secret_key)


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


def is_travis():
    return os.environ['QINIU_TEST_ENV'] == 'travis'


class UtilsTest(unittest.TestCase):
    def test_urlsafe(self):
        a = 'hello\x96'
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

    def test_verify_callback(self):
        body = 'name=sunflower.jpg&hash=Fn6qeQi4VDLQ347NiRm-RlQx_4O2&location=Shanghai&price=1500.00&uid=123'
        url = 'test.qiniu.com/callback'
        ok = dummy_auth.verify_callback('QBox abcdefghklmnopq:ZWyeM5ljWMRFwuPTPOwQ4RwSto4=', url, body)
        assert ok


class BucketTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)
    bucket = BucketManager(q)

    def test_list(self):
        ret, eof, info = self.bucket.list(bucket_name, limit=4)
        print(info)
        assert eof is False
        assert len(ret.get('items')) == 4
        ret, eof, info = self.bucket.list(bucket_name, limit=1000)
        print(info)
        assert eof is True

    def test_buckets(self):
        ret, info = self.bucket.buckets()
        print(info)
        assert bucket_name in ret

    def test_prefetch(self):
        ret, info = self.bucket.prefetch(bucket_name, 'python-sdk.html')
        print(info)
        assert ret['key'] == 'python-sdk.html'

    def test_fetch(self):
        ret, info = self.bucket.fetch('http://developer.qiniu.com/docs/v6/sdk/python-sdk.html', bucket_name,
                                      'fetch.html')
        print(info)
        assert ret['key'] == 'fetch.html'
        assert 'hash' in ret

    def test_fetch_without_key(self):
        ret, info = self.bucket.fetch('http://developer.qiniu.com/docs/v6/sdk/python-sdk.html', bucket_name)
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


class UploaderTestCase(unittest.TestCase):
    mime_type = "text/plain"
    params = {'x:a': 'a'}
    q = Auth(access_key, secret_key)

    def test_put(self):
        key = 'a\\b\\c"hello'
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['key'] == key

    def test_put_crc(self):
        key = ''
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name, key)
        ret, info = put_data(token, key, data, check_crc=True)
        print(info)
        assert ret['key'] == key

    def test_putfile(self):
        localfile = __file__
        key = 'test_file'

        token = self.q.upload_token(bucket_name, key)
        ret, info = put_file(token, key, localfile, mime_type=self.mime_type, check_crc=True)
        print(info)
        assert ret['key'] == key
        assert ret['hash'] == etag(localfile)

    def test_putInvalidCrc(self):
        key = 'test_invalid'
        data = 'hello bubby!'
        crc32 = 'wrong crc32'
        token = self.q.upload_token(bucket_name)
        ret, info = _form_put(token, key, data, None, None, crc=crc32)
        print(info)
        assert ret is None
        assert info.status_code == 400

    def test_putWithoutKey(self):
        key = None
        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['hash'] == ret['key']

        data = 'hello bubby!'
        token = self.q.upload_token(bucket_name, 'nokey2')
        ret, info = put_data(token, None, data)
        print(info)
        assert ret is None
        assert info.status_code == 403  # key not match

    def test_withoutRead_withoutSeek_retry(self):
        key = 'retry'
        data = 'hello retry!'
        set_default(default_zone=Zone('http://a', 'http://upload.qiniu.com'))
        token = self.q.upload_token(bucket_name)
        ret, info = put_data(token, key, data)
        print(info)
        assert ret['key'] == key
        assert ret['hash'] == 'FlYu0iBR1WpvYi4whKXiBuQpyLLk'

    def test_putData_without_fname(self):
        if is_travis():
            return
        localfile = create_temp_file(30 * 1024 * 1024)
        key = 'test_putData_without_fname'
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name)
            ret, info = put_data(token, key, input_stream)
            print(info)
            assert ret is not None

    def test_putData_without_fname1(self):
        if is_travis():
            return
        localfile = create_temp_file(30 * 1024 * 1024)
        key = 'test_putData_without_fname1'
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name)
            ret, info = put_data(token, key, input_stream, self.params, self.mime_type, False, None, "")
            print(info)
            assert ret is not None

    def test_putData_without_fname2(self):
        if is_travis():
            return
        localfile = create_temp_file(30 * 1024 * 1024)
        key = 'test_putData_without_fname2'
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name)
            ret, info = put_data(token, key, input_stream, self.params, self.mime_type, False, None, "  ")
            print(info)
            assert ret is not None


class ResumableUploaderTestCase(unittest.TestCase):
    mime_type = "text/plain"
    params = {'x:a': 'a'}
    q = Auth(access_key, secret_key)

    def test_put_stream(self):
        localfile = __file__
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, self.params,
                                   self.mime_type)
            print(info)
            assert ret['key'] == key

    def test_big_file(self):
        key = 'big'
        token = self.q.upload_token(bucket_name, key)
        localfile = create_temp_file(4 * 1024 * 1024 + 1)
        progress_handler = lambda progress, total: progress
        qiniu.set_default(default_zone=Zone('http://a', 'http://upload.qiniu.com'))
        ret, info = put_file(token, key, localfile, self.params, self.mime_type, progress_handler=progress_handler)
        print(info)
        assert ret['key'] == key
        remove_temp_file(localfile)

    def test_retry(self):
        localfile = __file__
        key = 'test_file_r_retry'
        qiniu.set_default(default_zone=Zone('http://a', 'http://upload.qiniu.com'))
        token = self.q.upload_token(bucket_name, key)
        ret, info = put_file(token, key, localfile, self.params, self.mime_type)
        print(info)
        assert ret['key'] == key
        assert ret['hash'] == etag(localfile)


class DownloadTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)

    def test_private_url(self):
        private_bucket = 'private-res'
        private_key = 'gogopher.jpg'
        base_url = 'http://%s/%s' % (private_bucket + '.qiniudn.com', private_key)
        private_url = self.q.private_download_url(base_url, expires=3600)
        print(private_url)
        r = requests.get(private_url)
        assert r.status_code == 200


class MediaTestCase(unittest.TestCase):
    def test_pfop(self):
        q = Auth(access_key, secret_key)
        pfop = PersistentFop(q, 'testres', 'sdktest')
        op = op_save('avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240', 'pythonsdk', 'pfoptest')
        ops = []
        ops.append(op)
        ret, info = pfop.execute('sintel_trailer.mp4', ops, 1)
        print(info)
        assert ret['persistentId'] is not None


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


class ReadWithoutSeek(object):
    def __init__(self, str):
        self.str = str
        pass

    def read(self):
        print(self.str)


if __name__ == '__main__':
    unittest.main()
