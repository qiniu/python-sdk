from qiniu.http.middleware import Middleware, RetryDomainsMiddleware
from qiniu.http import qn_http_client


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


class TestMiddleware:
    def test_middlewares(self, mock_server_addr):
        rec_ls = []
        mw_a = MiddlewareRecorder(rec_ls, 'A')
        mw_b = MiddlewareRecorder(rec_ls, 'B')
        qn_http_client.get(
            '{scheme}://{host}/echo?status=200'.format(
                scheme=mock_server_addr.scheme,
                host=mock_server_addr.netloc
            ),
            middlewares=[
                mw_a,
                mw_b
            ]
        )
        assert rec_ls == ['bef_A0', 'bef_B1', 'aft_B2', 'aft_A3']

    def test_retry_domains(self, mock_server_addr):
        rec_ls = []
        mw_rec = MiddlewareRecorder(rec_ls, 'rec')
        ret, resp = qn_http_client.get(
            '{scheme}://fake.pysdk.qiniu.com/echo?status=200'.format(
                scheme=mock_server_addr.scheme
            ),
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=[
                        'unavailable.pysdk.qiniu.com',
                        mock_server_addr.netloc
                    ],
                    max_retry_times=3
                ),
                mw_rec
            ]
        )
        # ['bef_rec0', 'bef_rec1', 'bef_rec2'] are 'fake.pysdk.qiniu.com' with retried 3 times
        # ['bef_rec3', 'bef_rec4', 'bef_rec5'] are 'unavailable.pysdk.qiniu.com' with retried 3 times
        # ['bef_rec6', 'aft_rec7'] are mock_server and it's success
        assert rec_ls == [
            'bef_rec0', 'bef_rec1', 'bef_rec2',
            'bef_rec3', 'bef_rec4', 'bef_rec5',
            'bef_rec6', 'aft_rec7'
        ]
        assert ret == {}
        assert resp.status_code == 200

    def test_retry_domains_fail_fast(self, mock_server_addr):
        rec_ls = []
        mw_rec = MiddlewareRecorder(rec_ls, 'rec')
        ret, resp = qn_http_client.get(
            '{scheme}://fake.pysdk.qiniu.com/echo?status=200'.format(
                scheme=mock_server_addr.scheme
            ),
            middlewares=[
                RetryDomainsMiddleware(
                    backup_domains=[
                        'unavailable.pysdk.qiniu.com',
                        mock_server_addr.netloc
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
