# -*- coding: utf-8 -*-
import io
import os

from qiniu.compat import is_py2, str as text_type

from .client import SandboxClient


def load_dotenv_if_present(*paths):
    if not paths:
        paths = (
            os.path.join(os.getcwd(), '.env'),
        )

    for path in paths:
        if not path or not os.path.exists(path):
            continue
        with io.open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = _strip_inline_comment(value.strip()).strip()
                if (
                    len(value) >= 2 and
                    value[0] == value[-1] and
                    value[0] in ('"', "'")
                ):
                    value = value[1:-1]
                if key and key not in os.environ:
                    key, value = _native_env_pair(key, value)
                    os.environ[key] = value


def _native_env_pair(key, value):
    if is_py2:
        if isinstance(key, text_type):
            key = key.encode('utf-8')
        if isinstance(value, text_type):
            value = value.encode('utf-8')
    return key, value


def _strip_inline_comment(value):
    quote = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            continue
        if char == '#' and (index == 0 or value[index - 1].isspace()):
            return value[:index]
    return value


def env(key, fallback=None):
    return os.getenv(key) or fallback


def first_env(*keys):
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def required_env(key):
    value = os.getenv(key)
    if value:
        return value
    raise RuntimeError('Please set {0}'.format(key))


def sandbox_endpoint():
    return env('QINIU_SANDBOX_ENDPOINT')


def sandbox_api_key():
    value = first_env(
        'QINIU_SANDBOX_API_KEY',
        'QINIU_API_KEY',
        'E2B_API_KEY',
    )
    if value:
        return value
    raise RuntimeError(
        'Please set QINIU_SANDBOX_API_KEY, QINIU_API_KEY, or E2B_API_KEY')


def sandbox_template():
    return env('QINIU_SANDBOX_TEMPLATE', 'base')


def sandbox_client(**options):
    defaults = {
        'endpoint': sandbox_endpoint(),
        'api_key': sandbox_api_key(),
    }
    access_key = env('QINIU_SANDBOX_ACCESS_KEY')
    secret_key = env('QINIU_SANDBOX_SECRET_KEY')
    if access_key and secret_key:
        defaults['access_key'] = access_key
        defaults['secret_key'] = secret_key
    defaults.update(options)
    return SandboxClient(**defaults)
