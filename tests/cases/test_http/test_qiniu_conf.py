import pytest
import requests

from qiniu.compat import urlencode
import qiniu.http as qiniu_http


@pytest.fixture(scope='function')
def retry_id(request, mock_server_addr):
    success_times = []
    failure_times = []
    if hasattr(request, 'param'):
        success_times = request.param.get('success_times', success_times)
        failure_times = request.param.get('failure_times', failure_times)
    query_dict = {
        's': success_times,
        'f': failure_times,
    }
    query_params = urlencode(
        query_dict,
        doseq=True
    )
    request_url = '{scheme}://{host}/retry_me/__mgr__?{query_params}'.format(
        scheme=mock_server_addr.scheme,
        host=mock_server_addr.netloc,
        query_params=query_params
    )
    resp = requests.put(request_url)
    resp.raise_for_status()
    record_id = resp.text
    yield record_id
    request_url = '{scheme}://{host}/retry_me/__mgr__?id={id}'.format(
        scheme=mock_server_addr.scheme,
        host=mock_server_addr.netloc,
        id=record_id
    )
    resp = requests.delete(request_url)
    resp.raise_for_status()


@pytest.fixture(scope='function')
def reset_session():
    qiniu_http._session = None
    yield


class TestQiniuConfWithHTTP:
    @pytest.mark.usefixtures('reset_session')
    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'connection_timeout': 0.3,
                'connection_retries': 0
            }
        ],
        indirect=True
    )
    @pytest.mark.parametrize(
        'method,opts',
        [
            ('get', {}),
            ('put', {'data': None, 'files': None}),
            ('post', {'data': None, 'files': None}),
            ('delete', {'params': None})
        ],
        ids=lambda v: v if type(v) is str else 'opts'
    )
    def test_timeout_conf(self, mock_server_addr, method, opts, set_conf_default):
        request_url = '{scheme}://{host}/timeout?delay=0.5'.format(
            scheme=mock_server_addr.scheme,
            host=mock_server_addr.netloc
        )
        send = getattr(qiniu_http.qn_http_client, method)
        _ret, resp = send(request_url, **opts)
        assert 'Read timed out' in str(resp.exception)

    @pytest.mark.usefixtures('reset_session')
    @pytest.mark.parametrize(
        'retry_id',
        [
            {
                'success_times': [0, 1],
                'failure_times': [5, 0],
            },
        ],
        indirect=True
    )
    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'connection_retries': 5
            }
        ],
        indirect=True
    )
    @pytest.mark.parametrize(
        'method,opts',
        [
            # post not retry default, see
            # https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#urllib3.util.Retry.DEFAULT_ALLOWED_METHODS
            ('get', {}),
            ('put', {'data': None, 'files': None}),
            ('delete', {'params': None})
        ],
        ids=lambda v: v if type(v) is str else 'opts'
    )
    def test_retry_times(self, retry_id, mock_server_addr, method, opts, set_conf_default):
        request_url = '{scheme}://{host}/retry_me?id={id}'.format(
            scheme=mock_server_addr.scheme,
            host=mock_server_addr.netloc,
            id=retry_id
        )
        send = getattr(qiniu_http.qn_http_client, method)
        _ret, resp = send(request_url, **opts)
        assert resp.status_code == 200
