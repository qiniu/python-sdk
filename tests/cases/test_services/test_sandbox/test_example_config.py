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


def test_examples_cover_primary_sandbox_surfaces():
    expected_examples = [
        'sandbox_commands.py',
        'sandbox_connect.py',
        'sandbox_create.py',
        'sandbox_filesystem.py',
        'sandbox_git.py',
        'sandbox_injection_rules.py',
        'sandbox_lifecycle.py',
        'sandbox_observability.py',
        'sandbox_resources.py',
        'sandbox_runtime.py',
        'sandbox_template_lifecycle.py',
        'sandbox_templates.py',
    ]
    for name in expected_examples:
        assert os.path.exists(os.path.join(ROOT, 'examples', name))

    checks = {
        'sandbox_commands.py': [
            'commands.start',
            'commands.list',
            'commands.send_stdin',
            'commands.close_stdin',
            'commands.kill',
            'commands.connect',
        ],
        'sandbox_filesystem.py': [
            'files.make_dir',
            'files.write(',
            'files.read(',
            'files.write_files',
            'files.get_info',
            'files.list',
            'files.rename',
            'files.remove',
        ],
        'sandbox_observability.py': [
            'wait_for_ready',
            'is_running',
            'get_host',
            'get_mcp_url',
            'get_mcp_token',
            'download_url',
            'upload_url',
            'get_metrics',
            'get_logs',
        ],
        'sandbox_template_lifecycle.py': [
            'list_default_templates',
            'list_templates',
            'get_template',
            'update_template',
            'assign_template_tags',
            'delete_template_tags',
            'get_template_build_status',
            'get_template_build_logs',
            'start_template_build',
            'wait_for_build',
            'delete_template',
        ],
        'sandbox_injection_rules.py': [
            'create_injection_rule',
            'list_injection_rules',
            'get_injection_rule',
            'update_injection_rule',
            'delete_injection_rule',
        ],
        'sandbox_lifecycle.py': [
            'set_timeout',
            'refresh',
            'pause',
            'resume',
            'update_network',
        ],
        'sandbox_resources.py': [
            'GitRepositoryResource',
            'push_branch_with_credentials',
            'KodoResource',
            'read_only=True',
        ],
    }

    for name, snippets in checks.items():
        content = read_project_file('examples', name)
        for snippet in snippets:
            assert snippet in content
