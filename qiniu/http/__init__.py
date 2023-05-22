# -*- coding: utf-8 -*-
import logging
import platform

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from qiniu import config, __version__
import qiniu.auth

from .client import HTTPClient
from .response import ResponseInfo
from .middleware import UserAgentMiddleware


qn_http_client = HTTPClient(
    middlewares=[
        UserAgentMiddleware(__version__)
    ]
)


_sys_info = '{0}; {1}'.format(platform.system(), platform.machine())
_python_ver = platform.python_version()

USER_AGENT = 'QiniuPython/{0} ({1}; ) Python/{2}'.format(
    __version__, _sys_info, _python_ver)

_session = None
_headers = {'User-Agent': USER_AGENT}


def __return_wrapper(resp):
    if resp.status_code != 200 or resp.headers.get('X-Reqid') is None:
        return None, ResponseInfo(resp)
    resp.encoding = 'utf-8'
    try:
        ret = resp.json()
    except ValueError:
        logging.debug("response body decode error: %s" % resp.text)
        ret = {}
    return ret, ResponseInfo(resp)


def _init():
    global _session
    if _session is None:
        _session = qn_http_client.session

    adapter = HTTPAdapter(
        pool_connections=config.get_default('connection_pool'),
        pool_maxsize=config.get_default('connection_pool'),
        max_retries=config.get_default('connection_retries'))
    _session.mount('http://', adapter)


def _post(url, data, files, auth, headers=None):
    if _session is None:
        _init()
    try:
        post_headers = _headers.copy()
        if headers is not None:
            for k, v in headers.items():
                post_headers.update({k: v})
        r = _session.post(
            url, data=data, files=files, auth=auth, headers=post_headers,
            timeout=config.get_default('connection_timeout'))
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)


def _put(url, data, files, auth, headers=None):
    if _session is None:
        _init()
    try:
        post_headers = _headers.copy()
        if headers is not None:
            for k, v in headers.items():
                post_headers.update({k: v})
        r = _session.put(
            url, data=data, files=files, auth=auth, headers=post_headers,
            timeout=config.get_default('connection_timeout'))
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)


def _get(url, params, auth, headers=None):
    if _session is None:
        _init()
    try:
        get_headers = _headers.copy()
        if headers is not None:
            for k, v in headers.items():
                get_headers.update({k: v})
        r = _session.get(
            url,
            params=params,
            auth=auth,
            timeout=config.get_default('connection_timeout'),
            headers=get_headers)
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)


class _TokenAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = 'UpToken {0}'.format(self.token)
        return r


def _post_with_token(url, data, token):
    return _post(url, data, None, _TokenAuth(token))


def _post_with_token_and_headers(url, data, token, headers):
    return _post(url, data, None, _TokenAuth(token), headers)


def _post_file(url, data, files):
    return _post(url, data, files, None)


def _post_with_auth(url, data, auth):
    return _post(url, data, None, qiniu.auth.RequestsAuth(auth))


def _get_with_auth(url, data, auth):
    return _get(url, data, qiniu.auth.RequestsAuth(auth))


def _post_with_auth_and_headers(url, data, auth, headers):
    return _post(url, data, None, qiniu.auth.RequestsAuth(auth), headers)


def _get_with_auth_and_headers(url, data, auth, headers):
    return _get(url, data, qiniu.auth.RequestsAuth(auth), headers)


def _post_with_qiniu_mac_and_headers(url, data, auth, headers):
    return _post(url, data, None, qiniu.auth.QiniuMacRequestsAuth(auth), headers)


def _put_with_auth(url, data, auth):
    return _put(url, data, None, qiniu.auth.RequestsAuth(auth))


def _put_with_token_and_headers(url, data, auth, headers):
    return _put(url, data, None, _TokenAuth(auth), headers)


def _put_with_auth_and_headers(url, data, auth, headers):
    return _put(url, data, None, qiniu.auth.RequestsAuth(auth), headers)


def _put_with_qiniu_mac_and_headers(url, data, auth, headers):
    return _put(url, data, None, qiniu.auth.QiniuMacRequestsAuth(auth), headers)


def _post_with_qiniu_mac(url, data, auth):
    qn_auth = qiniu.auth.QiniuMacRequestsAuth(
        auth
    ) if auth is not None else None

    return _post(url, data, None, qn_auth)


def _get_with_qiniu_mac(url, params, auth):
    qn_auth = qiniu.auth.QiniuMacRequestsAuth(
        auth
    ) if auth is not None else None

    return _get(url, params, qn_auth)


def _get_with_qiniu_mac_and_headers(url, params, auth, headers):
    try:
        post_headers = _headers.copy()
        if headers is not None:
            for k, v in headers.items():
                post_headers.update({k: v})
        r = requests.get(
            url,
            params=params,
            auth=qiniu.auth.QiniuMacRequestsAuth(auth) if auth is not None else None,
            timeout=config.get_default('connection_timeout'),
            headers=post_headers)
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)


def _delete_with_qiniu_mac(url, params, auth):
    try:
        r = requests.delete(
            url,
            params=params,
            auth=qiniu.auth.QiniuMacRequestsAuth(auth) if auth is not None else None,
            timeout=config.get_default('connection_timeout'),
            headers=_headers)
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)


def _delete_with_qiniu_mac_and_headers(url, params, auth, headers):
    try:
        post_headers = _headers.copy()
        if headers is not None:
            for k, v in headers.items():
                post_headers.update({k: v})
        r = requests.delete(
            url,
            params=params,
            auth=qiniu.auth.QiniuMacRequestsAuth(auth) if auth is not None else None,
            timeout=config.get_default('connection_timeout'),
            headers=post_headers)
    except Exception as e:
        return None, ResponseInfo(None, e)
    return __return_wrapper(r)
