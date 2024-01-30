import requests

from qiniu.http import qn_http_client, __return_wrapper as return_wrapper


class TestResponse:
    def test_response_need_retry(self, mock_server_addr):
        def gen_case(code):
            if 0 <= code < 500:
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
            req_url = '{scheme}://{host}/echo?status={status}'.format(
                scheme=mock_server_addr.scheme,
                host=mock_server_addr.netloc,
                status=test_code
            )
            if test_code < 0:
                req_url = 'http://fake.python-sdk.qiniu.com/'
            _ret, resp_info = qn_http_client.get(req_url)
            assert_msg = '{code} should{adv} retry'.format(
                code=test_code,
                adv='' if should_retry else ' NOT'
            )
            assert resp_info.need_retry() == should_retry, assert_msg

    def test_json_decode_error(self, mock_server_addr):
        req_url = '{scheme}://{host}/echo?status=200'.format(
            scheme=mock_server_addr.scheme,
            host=mock_server_addr.netloc
        )
        ret, resp = qn_http_client.get(req_url)
        assert resp.text_body is not None
        assert ret == {}

    def test_old_json_decode_error(self):
        """
        test old return_wrapper
        """

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
