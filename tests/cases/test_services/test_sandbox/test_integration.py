# -*- coding: utf-8 -*-
import os

import pytest

from qiniu.services.sandbox import Sandbox, SandboxClient
from qiniu.services.sandbox.config import load_dotenv_if_present


load_dotenv_if_present()


def integration_client():
    if not os.getenv('QINIU_SANDBOX_API_KEY'):
        pytest.skip('QINIU_SANDBOX_API_KEY is required')
    return SandboxClient()


def test_create_run_filesystem_and_kill_sandbox():
    sandbox = None
    client = integration_client()
    template = os.getenv('QINIU_SANDBOX_TEMPLATE', 'base')
    try:
        sandbox = Sandbox.create(
            template,
            timeout=300,
            metadata={'sdk': 'python', 'test': 'integration'},
            envs={'QINIU_SANDBOX_TEST': '1'},
            client=client,
        )
        result = sandbox.commands.run('printf hello')
        assert result.exit_code == 0
        assert result.stdout == 'hello'

        sandbox.files.write('/tmp/qiniu-python-sdk.txt', 'hello')
        assert sandbox.files.read_text('/tmp/qiniu-python-sdk.txt') == 'hello'
    finally:
        if sandbox is not None:
            sandbox.kill()


def test_list_and_connect_existing_sandbox():
    client = integration_client()
    page = Sandbox.list(client=client, limit=5).next_items()
    assert isinstance(page, list)
    if not page:
        pytest.skip('No sandbox available to connect')

    connected = Sandbox.connect(page[0].sandbox_id, client=client, timeout=60)
    assert connected.sandbox_id == page[0].sandbox_id
