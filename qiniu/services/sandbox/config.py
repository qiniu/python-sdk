# -*- coding: utf-8 -*-
import io
import os

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
                value = value.strip()
                if (
                    len(value) >= 2 and
                    value[0] == value[-1] and
                    value[0] in ('"', "'")
                ):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value


def env(key, fallback=None):
    return os.getenv(key) or fallback


def required_env(key):
    value = os.getenv(key)
    if value:
        return value
    raise RuntimeError('Please set {0}'.format(key))


def sandbox_endpoint():
    return env('QINIU_SANDBOX_ENDPOINT')


def sandbox_api_key():
    return required_env('QINIU_SANDBOX_API_KEY')


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
