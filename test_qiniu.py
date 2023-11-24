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
from qiniu import put_data, put_file, put_stream
from qiniu import BucketManager, build_batch_copy, build_batch_rename, build_batch_move, build_batch_stat, \
    build_batch_delete, DomainManager
from qiniu import urlsafe_base64_encode, urlsafe_base64_decode, canonical_mime_header_key

from qiniu.compat import is_py2, is_py3, b, json

from qiniu.services.storage.uploader import _form_put

from qiniu.http import __return_wrapper as return_wrapper, qn_http_client
from qiniu.http.middleware import Middleware, RetryDomainsMiddleware

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

if hasattr(functools, 'cache'):
    cache_decorator = functools.cache
else:
    def cache_decorator(func):
        cache = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in cache:
                return cache[key]
            result = func(*args, **kwargs)
            cache[key] = result
            return result

        return wrapper

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')
hostscache_dir = None


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


class MiddlewareRecorder(Middleware):
    def __init__(self, rec, label):
        self.rec = rec
        self.label = label

    def __call__(self, request, nxt):
        self.rec.append(
            'bef_{0}{1}'.format(self.label, len(self.rec))
        )
        resp = nxt(request)
        self.rec.append(
            'aft_{0}{1}'.format(self.label, len(self.rec))
        )
        return resp


class HttpTest(unittest.TestCase):
    def test_response_need_retry(self):
        _ret, resp_info = qn_http_client.get('https://qiniu.com/index.html')

        resp_info.req_id = 'mocked-req-id'
        resp_info.error = None

        def gen_case(code):
            if 0 < code < 500:
                return code, False
            if code in [
                501, 509, 573, 579, 608, 612, 614, 616, 618, 630, 631, 632, 640, 701
            ]:
                return code, False
            return code, True

        cases = [
            gen_case(i) for i in range(-1, 800)
        ]

        for test_code, should_retry in cases:
            resp_info.status_code = test_code
            assert_msg = '{0} should{1} retry'.format(test_code, '' if should_retry else ' NOT')
            assert resp_info.need_retry() == should_retry, assert_msg

    def test_middlewares(self):
        rec_ls = []
        mw_a = MiddlewareRecorder(rec_ls, 'A')
        mw_b = MiddlewareRecorder(rec_ls, 'B')
        qn_http_client.get(
            'https://qiniu.com/index.html',
            middlewares=[
                mw_a,
                mw_b
            ]
        )
        assert rec_ls == ['bef_A0', 'bef_B1', 'aft_B2', 'aft_A3']


    def test_retry_domains(self):
        rec_ls = []
        mw_rec = MiddlewareRecorder(rec_ls, 'rec')
        ret, resp = qn_http_client.get(
            'https://fake.pysdk.qiniu.com/index.html',
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=[
                        'unavailable.pysdk.qiniu.com',
                        'qiniu.com'
                    ],
                    max_retry_times=3
                ),
                mw_rec
            ]
        )
        # ['bef_rec0', 'bef_rec1', 'bef_rec2'] are 'fake.pysdk.qiniu.com' with retried 3 times
        # ['bef_rec3', 'bef_rec4', 'bef_rec5'] are 'unavailable.pysdk.qiniu.com' with retried 3 times
        # ['bef_rec6', 'aft_rec7'] are 'qiniu.com' and it's success
        assert rec_ls == [
            'bef_rec0', 'bef_rec1', 'bef_rec2',
            'bef_rec3', 'bef_rec4', 'bef_rec5',
            'bef_rec6', 'aft_rec7'
        ]
        assert ret == {}
        assert resp.status_code == 200

    def test_retry_domains_fail_fast(self):
        rec_ls = []
        mw_rec = MiddlewareRecorder(rec_ls, 'rec')
        ret, resp = qn_http_client.get(
            'https://fake.pysdk.qiniu.com/index.html',
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=[
                        'unavailable.pysdk.qiniu.com',
                        'qiniu.com'
                    ],
                    retry_condition=lambda _resp, _req: False
                ),
                mw_rec
            ]
        )
        # ['bef_rec0'] are 'fake.pysdk.qiniu.com' with fail fast
        assert rec_ls == ['bef_rec0']
        assert ret is None
        assert resp.status_code == -1



    def test_json_decode_error(self):
        def mock_res():
            r = requests.Response()
            r.status_code = 200
            r.headers.__setitem__('X-Reqid', 'mockedReqid')

            def json_func():
                raise ValueError('%s: line %d column %d (char %d)' % ('Expecting value', 0, 0, 0))
            r.json = json_func

            return r
        mocked_res = mock_res()
        ret, _ = return_wrapper(mocked_res)
        assert ret == {}


class UtilsTest(unittest.TestCase):
    def test_urlsafe(self):
        a = 'hello\x96'
        u = urlsafe_base64_encode(a)
        assert b(a) == urlsafe_base64_decode(u)

    def test_canonical_mime_header_key(self):
        field_names = [
            ":status",
            ":x-test-1",
            ":x-Test-2",
            "content-type",
            "CONTENT-LENGTH",
            "oRiGin",
            "ReFer",
            "Last-Modified",
            "acCePt-ChArsEt",
            "x-test-3",
            "cache-control",
        ]
        expect_canonical_field_names = [
            ":status",
            ":x-test-1",
            ":x-Test-2",
            "Content-Type",
            "Content-Length",
            "Origin",
            "Refer",
            "Last-Modified",
            "Accept-Charset",
            "X-Test-3",
            "Cache-Control",
        ]
        assert len(field_names) == len(expect_canonical_field_names)
        for i in range(len(field_names)):
            assert canonical_mime_header_key(field_names[i]) == expect_canonical_field_names[i]


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
        token = dummy_auth.token_of_request('https://www.qiniu.com?go=1', 'test', '')
        assert token == 'abcdefghklmnopq:cFyRVoWrE3IugPIMP5YJFTO-O-Y='
        token = dummy_auth.token_of_request('https://www.qiniu.com?go=1', 'test', 'application/x-www-form-urlencoded')
        assert token == 'abcdefghklmnopq:svWRNcacOE-YMsc70nuIYdaa1e4='

    def test_QiniuMacRequestsAuth(self):
        auth = QiniuMacAuth("ak", "sk")
        test_cases = [
            {
                "method": "GET",
                "host": None,
                "url": "",
                "qheaders": {
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "{\"name\": \"test\"}",
                "except_sign_token": "ak:0i1vKClRDWFyNkcTFzwcE7PzX74=",
            },
            {
                "method": "GET",
                "host": None,
                "url": "",
                "qheaders": {
                    "Content-Type": "application/json",
                },
                "content_type": "application/json",
                "body": "{\"name\": \"test\"}",
                "except_sign_token": "ak:K1DI0goT05yhGizDFE5FiPJxAj4=",
            },
            {
                "method": "POST",
                "host": None,
                "url": "",
                "qheaders": {
                    "Content-Type": "application/json",
                    "X-Qiniu": "b",
                },
                "content_type": "application/json",
                "body": "{\"name\": \"test\"}",
                "except_sign_token": "ak:0ujEjW_vLRZxebsveBgqa3JyQ-w=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com",
                "qheaders": {
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "{\"name\": \"test\"}",
                "except_sign_token": "ak:GShw5NitGmd5TLoo38nDkGUofRw=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com",
                "qheaders": {
                    "Content-Type": "application/json",
                    "X-Qiniu-Bbb": "BBB",
                    "X-Qiniu-Aaa": "DDD",
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                },
                "content_type": "application/json",
                "body": "{\"name\": \"test\"}",
                "except_sign_token": "ak:DhNA1UCaBqSHCsQjMOLRfVn63GQ=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com",
                "qheaders": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Qiniu-Bbb": "BBB",
                    "X-Qiniu-Aaa": "DDD",
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "name=test&language=go",
                "except_sign_token": "ak:KUAhrYh32P9bv0COD8ugZjDCmII=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com",
                "qheaders": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Qiniu-Bbb": "BBB",
                    "X-Qiniu-Aaa": "DDD",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "name=test&language=go",
                "except_sign_token": "ak:KUAhrYh32P9bv0COD8ugZjDCmII=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com/mkfile/sdf.jpg",
                "qheaders": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Qiniu-Bbb": "BBB",
                    "X-Qiniu-Aaa": "DDD",
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "name=test&language=go",
                "except_sign_token": "ak:fkRck5_LeyfwdkyyLk-hyNwGKac=",
            },
            {
                "method": "GET",
                "host": "upload.qiniup.com",
                "url": "http://upload.qiniup.com/mkfile/sdf.jpg?s=er3&df",
                "qheaders": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Qiniu-Bbb": "BBB",
                    "X-Qiniu-Aaa": "DDD",
                    "X-Qiniu-": "a",
                    "X-Qiniu": "b",
                },
                "content_type": "application/x-www-form-urlencoded",
                "body": "name=test&language=go",
                "except_sign_token": "ak:PUFPWsEUIpk_dzUvvxTTmwhp3p4=",
            },
        ]

        for test_case in test_cases:
            sign_token = auth.token_of_request(
                method=test_case["method"],
                host=test_case["host"],
                url=test_case["url"],
                qheaders=auth.qiniu_headers(test_case["qheaders"]),
                content_type=test_case["content_type"],
                body=test_case["body"],
            )
            assert sign_token == test_case["except_sign_token"]

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
        assert eof is False
        assert len(ret.get('items')) == 4
        ret, eof, info = self.bucket.list(bucket_name, limit=1000)
        print(ret, eof, info)
        assert info.status_code == 200

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
        os.unsetenv('DISABLE_QINIU_TIMESTAMP_SIGNATURE')
        assert 'hash' in ret

    @freeze_time("1970-01-01")
    def test_invalid_x_qiniu_date_env_be_ignored(self):
        os.environ['DISABLE_QINIU_TIMESTAMP_SIGNATURE'] = 'True'
        q = Auth(access_key, secret_key, disable_qiniu_timestamp_signature=False)
        bucket = BucketManager(q)
        ret, info = bucket.stat(bucket_name, 'python-sdk.html')
        os.unsetenv('DISABLE_QINIU_TIMESTAMP_SIGNATURE')
        assert ret is None
        assert info.status_code == 403


@cache_decorator
def get_valid_up_host():
    zone = Zone()
    try:
        hosts = json.loads(
            zone.bucket_hosts(access_key, bucket_name)
        ).get('hosts')
        up_host = 'https://' + hosts[0].get('up', {}).get('domains')[0]
    except IndexError:
        up_host = 'https://upload.qiniup.com'
    return up_host


class UploaderTestCase(unittest.TestCase):
    mime_type = "text/plain"
    params = {'x:a': 'a'}
    metadata = {
        'x-qn-meta-name': 'qiniu',
        'x-qn-meta-age': '18'
    }
    q = Auth(access_key, secret_key)
    bucket = BucketManager(q)

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
        try:
            key = 'retry'
            data = 'hello retry!'
            up_host_backup = get_valid_up_host()
            set_default(default_zone=Zone('http://a', up_host_backup))
            token = self.q.upload_token(bucket_name)
            ret, info = put_data(token, key, data)
            print(info)
            assert ret['key'] == key
            assert ret['hash'] == 'FlYu0iBR1WpvYi4whKXiBuQpyLLk'
        finally:
            set_default(default_zone=Zone())
            qiniu.config._is_customized_default['default_zone'] = False

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

    def test_put_file_with_metadata(self):
        localfile = __file__
        key = 'test_file_with_metadata'

        token = self.q.upload_token(bucket_name, key)
        ret, info = put_file(token, key, localfile, metadata=self.metadata)
        assert ret['key'] == key
        assert ret['hash'] == etag(localfile)
        ret, info = self.bucket.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    def test_put_data_with_metadata(self):
        key = 'put_data_with_metadata'
        data = 'hello metadata!'
        token = self.q.upload_token(bucket_name, key)
        ret, info = put_data(token, key, data, metadata=self.metadata)
        assert ret['key'] == key
        ret, info = self.bucket.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'


class ResumableUploaderTestCase(unittest.TestCase):
    mime_type = "text/plain"
    params = {'x:a': 'a'}
    metadata = {
        'x-qn-meta-name': 'qiniu',
        'x-qn-meta-age': '18'
    }
    q = Auth(access_key, secret_key)
    bucket = BucketManager(q)

    def test_put_stream(self):
        localfile = __file__
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=None, version=None, bucket_name=None)
            assert ret['key'] == key

    def test_put_stream_v2_without_bucket_name(self):
        localfile = __file__
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=1024 * 1024 * 10, version='v2')
            assert ret['key'] == key

    def test_put_2m_stream_v2(self):
        localfile = create_temp_file(2 * 1024 * 1024 + 1)
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=1024 * 1024 * 4, version='v2', bucket_name=bucket_name)
            assert ret['key'] == key
            remove_temp_file(localfile)

    def test_put_4m_stream_v2(self):
        localfile = create_temp_file(4 * 1024 * 1024)
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=1024 * 1024 * 4, version='v2', bucket_name=bucket_name)
            assert ret['key'] == key
            remove_temp_file(localfile)

    def test_put_10m_stream_v2(self):
        localfile = create_temp_file(10 * 1024 * 1024 + 1)
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=1024 * 1024 * 4, version='v2', bucket_name=bucket_name)
            assert ret['key'] == key
            remove_temp_file(localfile)

    def test_put_stream_v2_without_key(self):
        part_size = 1024 * 1024 * 4
        localfile = create_temp_file(part_size + 1)
        key = None
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=part_size, version='v2', bucket_name=bucket_name)
            assert ret['key'] == ret['hash']
            remove_temp_file(localfile)

    def test_put_stream_v2_with_empty_return_body(self):
        part_size = 1024 * 1024 * 4
        localfile = create_temp_file(part_size + 1)
        key = 'test_file_empty_return_body'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key, policy={'returnBody': ' '})
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params,
                                   self.mime_type, part_size=part_size, version='v2', bucket_name=bucket_name)
            assert info.status_code == 200
            assert ret == {}
            remove_temp_file(localfile)

    def test_big_file(self):
        key = 'big'
        token = self.q.upload_token(bucket_name, key)
        localfile = create_temp_file(4 * 1024 * 1024 + 1)
        progress_handler = lambda progress, total: progress
        ret, info = put_file(token, key, localfile, self.params, self.mime_type, progress_handler=progress_handler)
        print(info)
        assert ret['key'] == key
        remove_temp_file(localfile)

    def test_retry(self):
        try:
            localfile = __file__
            key = 'test_file_r_retry'
            token = self.q.upload_token(bucket_name, key)
            up_host_backup = get_valid_up_host()
            set_default(default_zone=Zone('http://a', up_host_backup))
            ret, info = put_file(token, key, localfile, self.params, self.mime_type)
            print(info)
            assert ret['key'] == key
            assert ret['hash'] == etag(localfile)
        finally:
            set_default(default_zone=Zone())
            qiniu.config._is_customized_default['default_zone'] = False

    def test_put_stream_with_key_limits(self):
        localfile = __file__
        key = 'test_file_r'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key, policy={'keylimit': ['test_file_d']})
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, hostscache_dir,
                                   self.params,
                                   self.mime_type)
            assert info.status_code == 403
            token = self.q.upload_token(bucket_name, key, policy={'keylimit': ['test_file_d', 'test_file_r']})
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, hostscache_dir,
                                   self.params,
                                   self.mime_type)
            assert info.status_code == 200

    def test_put_stream_with_metadata(self):
        localfile = __file__
        key = 'test_put_stream_with_metadata'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(__file__), size, hostscache_dir,
                                   self.params, self.mime_type,
                                   part_size=None, version=None, bucket_name=None, metadata=self.metadata)
            assert ret['key'] == key
        ret, info = self.bucket.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'

    def test_put_stream_v2_with_metadata(self):
        part_size = 1024 * 1024 * 4
        localfile = create_temp_file(part_size + 1)
        key = 'test_put_stream_v2_with_metadata'
        size = os.stat(localfile).st_size
        with open(localfile, 'rb') as input_stream:
            token = self.q.upload_token(bucket_name, key)
            ret, info = put_stream(token, key, input_stream, os.path.basename(localfile), size, hostscache_dir,
                                   self.params, self.mime_type,
                                   part_size=part_size, version='v2', bucket_name=bucket_name, metadata=self.metadata)
            assert ret['key'] == key
            remove_temp_file(localfile)
        ret, info = self.bucket.stat(bucket_name, key)
        assert 'x-qn-meta' in ret
        assert ret['x-qn-meta']['name'] == 'qiniu'
        assert ret['x-qn-meta']['age'] == '18'


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


class CdnTestCase(unittest.TestCase):
    q = Auth(access_key, secret_key)
    domain_manager = DomainManager(q)

    def test_get_domain(self):
        ret, info = self.domain_manager.get_domain('pythonsdk.qiniu.io')
        print(info)
        assert info.status_code == 200


class RegionTestCase(unittest.TestCase):
    test_rs_host = 'test.region.compatible.config.rs'
    test_rsf_host = 'test.region.compatible.config.rsf'

    @staticmethod
    def restore_hosts():
        set_default(
            default_rs_host=qiniu.config.RS_HOST,
            default_rsf_host=qiniu.config.RSF_HOST,
            default_uc_host=qiniu.config.UC_HOST,
            default_query_region_host=qiniu.config.QUERY_REGION_HOST,
            default_query_region_backup_hosts=[
                'uc.qbox.me',
                'api.qiniu.com'
            ]
        )
        qiniu.config._is_customized_default['default_rs_host'] = False
        qiniu.config._is_customized_default['default_rsf_host'] = False
        qiniu.config._is_customized_default['default_uc_host'] = False
        qiniu.config._is_customized_default['default_query_region_host'] = False
        qiniu.config._is_customized_default['default_query_region_backup_hosts'] = False

    def test_config_compatible(self):
        try:
            set_default(default_rs_host=self.test_rs_host)
            set_default(default_rsf_host=self.test_rsf_host)
            zone = Zone()
            assert zone.get_rs_host("mock_ak", "mock_bucket") == self.test_rs_host
            assert zone.get_rsf_host("mock_ak", "mock_bucket") == self.test_rsf_host
        finally:
            RegionTestCase.restore_hosts()

    def test_query_region_with_custom_domain(self):
        try:
            set_default(
                default_query_region_host='https://fake-uc.phpsdk.qiniu.com'
            )
            zone = Zone()
            data = zone.bucket_hosts(access_key, bucket_name)
            assert data != 'null'
        finally:
            RegionTestCase.restore_hosts()

    def test_query_region_with_backup_domains(self):
        try:
            set_default(
                default_query_region_host='https://fake-uc.phpsdk.qiniu.com',
                default_query_region_backup_hosts=[
                    'unavailable-uc.phpsdk.qiniu.com',
                    'uc.qbox.me'
                ]
            )
            zone = Zone()
            data = zone.bucket_hosts(access_key, bucket_name)
            assert data != 'null'
        finally:
            RegionTestCase.restore_hosts()

    def test_query_region_with_uc_and_backup_domains(self):
        try:
            set_default(
                default_uc_host='https://fake-uc.phpsdk.qiniu.com',
                default_query_region_backup_hosts=[
                    'unavailable-uc.phpsdk.qiniu.com',
                    'uc.qbox.me'
                ]
            )
            zone = Zone()
            data = zone.bucket_hosts(access_key, bucket_name)
            assert data != 'null'
        finally:
            RegionTestCase.restore_hosts()


class ReadWithoutSeek(object):
    def __init__(self, str):
        self.str = str
        pass

    def read(self):
        print(self.str)


if __name__ == '__main__':
    unittest.main()
