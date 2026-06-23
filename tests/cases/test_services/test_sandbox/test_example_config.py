# -*- coding: utf-8 -*-
import os


ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')
)


def read_project_file(*parts):
    with open(os.path.join(ROOT, *parts), 'r') as f:
        return f.read()


def test_env_example_only_contains_connection_and_resource_inputs():
    content = read_project_file('.env.example')

    assert 'QINIU_SANDBOX_RUN_INTEGRATION' not in content
    assert 'QINIU_SANDBOX_TEST_TIMEOUT' not in content
    assert 'QINIU_SANDBOX_ID' not in content
    assert 'QINIU_SANDBOX_KODO_READ_ONLY' not in content


def test_examples_handle_runtime_branches_in_code():
    connect = read_project_file('examples', 'sandbox_connect.py')
    resources = read_project_file('examples', 'sandbox_resources.py')
    runtime = read_project_file('examples', 'sandbox_runtime.py')
    integration = read_project_file(
        'tests',
        'cases',
        'test_services',
        'test_sandbox',
        'test_integration.py',
    )

    assert 'QINIU_SANDBOX_ID' not in connect
    assert 'QINIU_SANDBOX_KODO_READ_ONLY' not in resources
    assert 'QINIU_SANDBOX_RUN_INTEGRATION' not in runtime
    assert 'QINIU_SANDBOX_TEST_TIMEOUT' not in runtime
    assert 'QINIU_SANDBOX_RUN_INTEGRATION' not in integration
    assert 'QINIU_SANDBOX_TEST_TIMEOUT' not in integration
