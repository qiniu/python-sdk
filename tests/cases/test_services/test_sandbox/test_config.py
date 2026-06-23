# -*- coding: utf-8 -*-
import os

import qiniu.services.sandbox.config as sandbox_config
from qiniu.services.sandbox.config import (
    load_dotenv_if_present,
    sandbox_client,
)


def test_load_dotenv_if_present_reads_key_values_without_overwriting(tmpdir):
    dotenv = tmpdir.join('.env')
    dotenv.write(
        '\n'.join([
            'QINIU_SANDBOX_API_KEY=from-file',
            'QINIU_SANDBOX_TEMPLATE="python:3.11"',
            'QINIU_SANDBOX_COMMENTED=value # inline comment',
            'QINIU_SANDBOX_HASH="value # not comment"',
            'EXISTING=value-from-file',
            '# ignored',
            '',
        ])
    )

    old = {
        key: os.environ.get(key)
        for key in (
            'QINIU_SANDBOX_API_KEY',
            'QINIU_SANDBOX_TEMPLATE',
            'QINIU_SANDBOX_COMMENTED',
            'QINIU_SANDBOX_HASH',
            'EXISTING',
        )
    }
    try:
        os.environ.pop('QINIU_SANDBOX_API_KEY', None)
        os.environ.pop('QINIU_SANDBOX_TEMPLATE', None)
        os.environ.pop('QINIU_SANDBOX_COMMENTED', None)
        os.environ.pop('QINIU_SANDBOX_HASH', None)
        os.environ['EXISTING'] = 'already-set'

        load_dotenv_if_present(str(dotenv))

        assert os.environ['QINIU_SANDBOX_API_KEY'] == 'from-file'
        assert os.environ['QINIU_SANDBOX_TEMPLATE'] == 'python:3.11'
        assert os.environ['QINIU_SANDBOX_COMMENTED'] == 'value'
        assert os.environ['QINIU_SANDBOX_HASH'] == 'value # not comment'
        assert os.environ['EXISTING'] == 'already-set'
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_sandbox_client_uses_loaded_env(tmpdir):
    dotenv = tmpdir.join('.env')
    dotenv.write('\n'.join([
        'QINIU_SANDBOX_API_KEY=api-key',
        'QINIU_SANDBOX_ENDPOINT=https://sandbox.example.test',
        'QINIU_SANDBOX_ACCESS_KEY=ak',
        'QINIU_SANDBOX_SECRET_KEY=sk',
    ]))

    old = {
        key: os.environ.get(key)
        for key in (
            'QINIU_SANDBOX_API_KEY',
            'QINIU_SANDBOX_ENDPOINT',
            'QINIU_SANDBOX_ACCESS_KEY',
            'QINIU_SANDBOX_SECRET_KEY',
        )
    }
    try:
        for key in old:
            os.environ.pop(key, None)
        load_dotenv_if_present(str(dotenv))

        client = sandbox_client()

        assert client.endpoint == 'https://sandbox.example.test'
        assert client.api_key == 'api-key'
        assert client.mac is not None
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_native_env_pair_encodes_unicode_on_python2(monkeypatch):
    monkeypatch.setattr(sandbox_config, 'is_py2', True)

    key, value = sandbox_config._native_env_pair(u'KEY', u'值')

    assert key == b'KEY'
    assert value == u'值'.encode('utf-8')
