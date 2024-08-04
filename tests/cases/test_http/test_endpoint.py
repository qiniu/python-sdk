from qiniu.http.endpoint import Endpoint


class TestEndpoint:
    def test_endpoint_with_default_scheme(self):
        endpoint = Endpoint('uc.python-sdk.qiniu.com')
        assert endpoint.get_value() == 'https://uc.python-sdk.qiniu.com'

    def test_endpoint_with_custom_scheme(self):
        endpoint = Endpoint('uc.python-sdk.qiniu.com', default_scheme='http')
        assert endpoint.get_value() == 'http://uc.python-sdk.qiniu.com'

    def test_endpoint_with_get_value_with_custom_scheme(self):
        endpoint = Endpoint('uc.python-sdk.qiniu.com', default_scheme='http')
        assert endpoint.get_value('https') == 'https://uc.python-sdk.qiniu.com'

    def test_create_endpoint_from_host_with_scheme(self):
        endpoint = Endpoint.from_host('http://uc.python-sdk.qiniu.com')
        assert endpoint.default_scheme == 'http'
        assert endpoint.get_value() == 'http://uc.python-sdk.qiniu.com'

    def test_clone_endpoint(self):
        endpoint = Endpoint('uc.python-sdk.qiniu.com')
        another_endpoint = endpoint.clone()
        another_endpoint.host = 'another-uc.python-sdk.qiniu.com'
        assert endpoint.get_value() == 'https://uc.python-sdk.qiniu.com'
        assert another_endpoint.get_value() == 'https://another-uc.python-sdk.qiniu.com'
