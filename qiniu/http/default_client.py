import functools

from requests.adapters import HTTPAdapter

from qiniu import config, __version__

from .client import HTTPClient
from .middleware import UserAgentMiddleware

qn_http_client = HTTPClient(
    middlewares=[
        UserAgentMiddleware(__version__)
    ]
)


# compatibility with some config from qiniu.config
def _before_send(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        _init_http_adapter()
        return func(self, *args, **kwargs)

    return wrapper


qn_http_client.send_request = _before_send(qn_http_client.send_request)


def _call_once(func):
    called = False
    result = None

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal called, result
        if called:
            return result
        result = func(*args, **kwargs)
        called = True
        return result

    return wrapper


@_call_once
def _init_http_adapter():
    adapter = HTTPAdapter(
        pool_connections=config.get_default('connection_pool'),
        pool_maxsize=config.get_default('connection_pool'),
        max_retries=config.get_default('connection_retries'))
    qn_http_client.session.mount('http://', adapter)
