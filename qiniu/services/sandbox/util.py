# -*- coding: utf-8 -*-
import base64
import hashlib
import json as std_json
import os
import posixpath
import time

from qiniu.compat import urlencode, urlparse

from .constants import DEFAULT_ENDPOINT, DEFAULT_USER


def normalize_endpoint(endpoint=None):
    endpoint = (
        endpoint or
        os.getenv('QINIU_SANDBOX_API_URL') or
        os.getenv('QINIU_SANDBOX_ENDPOINT') or
        os.getenv('E2B_API_URL') or
        DEFAULT_ENDPOINT
    )
    return endpoint.rstrip('/')


def encode_path(value):
    from qiniu.compat import is_py2
    if is_py2:
        from urllib import quote
    else:
        from urllib.parse import quote
    return quote(str(value), safe='')


def append_query(path, query=None):
    query = query or {}
    normalized = {}
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ','.join([str(item) for item in value])
        normalized[key] = value
    if not normalized:
        return path
    return path + '?' + urlencode(normalized)


def json_dumps(data):
    return std_json.dumps(data, separators=(',', ':'))


def timeout_seconds_from_options(opts):
    opts = opts or {}
    if opts.get('timeout') is not None:
        return opts.get('timeout')
    if opts.get('timeout_ms') is not None:
        return int((opts.get('timeout_ms') + 999) / 1000)
    if opts.get('timeoutMs') is not None:
        return int((opts.get('timeoutMs') + 999) / 1000)
    return None


def basic_auth(user=None):
    user = user or DEFAULT_USER
    raw = ('{0}:'.format(user)).encode('utf-8')
    return 'Basic {0}'.format(base64.b64encode(raw).decode('ascii'))


def file_signature(path, operation, user, access_token, expiration):
    raw = '{0}:{1}:{2}:{3}:{4}'.format(
        path, operation, user, access_token, expiration
    )
    return 'v1_{0}'.format(hashlib.sha256(raw.encode('utf-8')).hexdigest())


def file_basename(path):
    return posixpath.basename(path.rstrip('/')) or 'file'


def shell_quote(value):
    try:
        from shlex import quote
    except ImportError:
        from pipes import quote
    return quote(str(value))


def utc_timestamp_after(seconds):
    return int(time.time()) + int(seconds)


def parse_json_response(response):
    if response.content in (None, b'', ''):
        return None
    return response.json()


def get_info_value(info, camel_key, snake_key=None):
    info = info or {}
    if camel_key in info:
        return info.get(camel_key)
    if snake_key and snake_key in info:
        return info.get(snake_key)
    return None


def parsed_url(url):
    return urlparse(url)
