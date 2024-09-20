import pytest

from qiniu.auth import Auth, QiniuMacAuth


@pytest.fixture(scope="module")
def dummy_auth():
    dummy_access_key = 'abcdefghklmnopq'
    dummy_secret_key = '1234567890'
    yield Auth(dummy_access_key, dummy_secret_key)


class TestAuth:
    def test_token(self, dummy_auth):
        token = dummy_auth.token('test')
        assert token == 'abcdefghklmnopq:mSNBTR7uS2crJsyFr2Amwv1LaYg='

    def test_token_with_data(self, dummy_auth):
        token = dummy_auth.token_with_data('test')
        assert token == 'abcdefghklmnopq:-jP8eEV9v48MkYiBGs81aDxl60E=:dGVzdA=='

    def test_nokey(self, dummy_auth):
        with pytest.raises(ValueError):
            Auth(None, None).token('nokey')
        with pytest.raises(ValueError):
            Auth('', '').token('nokey')

    def test_token_of_request(self, dummy_auth):
        token = dummy_auth.token_of_request('https://www.qiniu.com?go=1', 'test', '')
        assert token == 'abcdefghklmnopq:cFyRVoWrE3IugPIMP5YJFTO-O-Y='
        token = dummy_auth.token_of_request('https://www.qiniu.com?go=1', 'test', 'application/x-www-form-urlencoded')
        assert token == 'abcdefghklmnopq:svWRNcacOE-YMsc70nuIYdaa1e4='

    @pytest.mark.parametrize(
        'opts, except_token',
        [
            (
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
                },
                "ak:0i1vKClRDWFyNkcTFzwcE7PzX74=",
            ),
            (
                {
                    "method": "GET",
                    "host": None,
                    "url": "",
                    "qheaders": {
                        "Content-Type": "application/json",
                    },
                    "content_type": "application/json",
                    "body": "{\"name\": \"test\"}",
                },
                "ak:K1DI0goT05yhGizDFE5FiPJxAj4=",
            ),
            (
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
                },
                "ak:0ujEjW_vLRZxebsveBgqa3JyQ-w=",
            ),
            (
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
                },
                "ak:GShw5NitGmd5TLoo38nDkGUofRw=",
            ),
            (
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
                },
                "ak:DhNA1UCaBqSHCsQjMOLRfVn63GQ=",
            ),
            (
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
                },
                "ak:KUAhrYh32P9bv0COD8ugZjDCmII=",
            ),
            (
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
                },
                "ak:KUAhrYh32P9bv0COD8ugZjDCmII=",
            ),
            (
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
                },
                "ak:fkRck5_LeyfwdkyyLk-hyNwGKac=",
            ),
            (
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
                },
                "ak:PUFPWsEUIpk_dzUvvxTTmwhp3p4=",
            )
        ]
    )
    def test_qiniu_mac_requests_auth(self, dummy_auth, opts, except_token):
        auth = QiniuMacAuth("ak", "sk")

        sign_token = auth.token_of_request(
            method=opts["method"],
            host=opts["host"],
            url=opts["url"],
            qheaders=auth.qiniu_headers(opts["qheaders"]),
            content_type=opts["content_type"],
            body=opts["body"],
        )
        assert sign_token == except_token

    def test_qbox_verify_callback(self, dummy_auth):
        ok = dummy_auth.verify_callback(
            'QBox abcdefghklmnopq:T7F-SjxX7X2zI4Fc1vANiNt1AUE=',
            url='https://test.qiniu.com/callback',
            body='name=sunflower.jpg&hash=Fn6qeQi4VDLQ347NiRm-RlQx_4O2&location=Shanghai&price=1500.00&uid=123'
        )
        assert ok

    def test_qiniu_verify_token(self, dummy_auth):
        ok = dummy_auth.verify_callback(
            'Qiniu abcdefghklmnopq:ZqS7EZuAKrhZaEIxqNGxDJi41IQ=',
            url='https://test.qiniu.com/callback',
            body='name=sunflower.jpg&hash=Fn6qeQi4VDLQ347NiRm-RlQx_4O2&location=Shanghai&price=1500.00&uid=123',
            content_type='application/x-www-form-urlencoded',
            method='GET',
            headers={
                'X-Qiniu-Bbb': 'BBB',
            }
        )
        assert ok

