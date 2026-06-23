# -*- coding: utf-8 -*-
import os

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
            'EXISTING',
        )
    }
    try:
        os.environ.pop('QINIU_SANDBOX_API_KEY', None)
        os.environ.pop('QINIU_SANDBOX_TEMPLATE', None)
        os.environ['EXISTING'] = 'already-set'

        load_dotenv_if_present(str(dotenv))

        assert os.environ['QINIU_SANDBOX_API_KEY'] == 'from-file'
        assert os.environ['QINIU_SANDBOX_TEMPLATE'] == 'python:3.11'
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
