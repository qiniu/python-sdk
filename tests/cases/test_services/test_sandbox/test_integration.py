# -*- coding: utf-8 -*-
import os
import time
import pytest

from qiniu.services.sandbox import (
    PtySize,
    Sandbox,
    SandboxClient,
    SandboxError,
)
from qiniu.services.sandbox.config import load_dotenv_if_present


load_dotenv_if_present()


def integration_client():
    if not os.getenv('QINIU_SANDBOX_API_KEY'):
        pytest.skip('QINIU_SANDBOX_API_KEY is required')
    return SandboxClient()


def is_unsupported_runtime_error(err):
    response = getattr(err, 'response', None)
    status_code = getattr(response, 'status_code', None)
    if status_code in (404, 501):
        return True
    message = str(err).lower()
    return (
        'unimplemented' in message or
        'not implemented' in message or
        'not found' in message
    )


def create_integration_sandbox(test_name):
    return Sandbox.create(
        os.getenv('QINIU_SANDBOX_TEMPLATE', 'base'),
        timeout=300,
        metadata={'sdk': 'python', 'test': test_name},
        envs={'QINIU_SANDBOX_TEST': '1'},
        client=integration_client(),
    )


def assert_command_ok(step, result):
    assert result.exit_code == 0, '{0} failed: {1}'.format(
        step, result.stderr or result.stdout or result.error)
    return result


def is_retryable_git_network_error(result):
    message = (result.stderr or result.stdout or result.error or '').lower()
    return result.exit_code != 0 and (
        'gnutls' in message or
        'tls connection' in message or
        'connection was non-properly terminated' in message or
        'the remote end hung up unexpectedly' in message
    )


def assert_git_network_ok(step, run, attempts=5):
    result = None
    for attempt in range(attempts):
        result = run()
        if result.exit_code == 0:
            return result
        if not is_retryable_git_network_error(result):
            return assert_command_ok(step, result)
        if attempt == attempts - 1:
            pytest.skip('{0} skipped due to external Git network error: {1}'
                        .format(step, result.stderr or result.stdout))
        time.sleep(attempt + 1)
    return assert_command_ok(step, result)


def remote_git_credentials():
    repo_url = os.getenv('GIT_REPO_URL')
    username = os.getenv('GIT_USERNAME')
    password = os.getenv('GIT_PASSWORD') or os.getenv('GITHUB_TOKEN')
    if password and not username:
        username = 'x-access-token'
    if not repo_url or not username or not password:
        pytest.skip('GIT_REPO_URL and Git credentials are required')
    return repo_url, username, password


def test_list_default_templates():
    templates = integration_client().list_default_templates()

    assert isinstance(templates, list)
    assert templates
    for template in templates:
        assert isinstance(template, dict)
        assert template.get('templateID')


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


def test_git_remote_push_when_credentials_are_configured():
    repo_url, username, password = remote_git_credentials()
    sandbox = None
    branch = 'python-sdk-it-{0}'.format(int(time.time() * 1000))
    repo_path = '/tmp/qiniu-python-sdk-remote-git'
    try:
        sandbox = create_integration_sandbox('remote_git')
        try:
            auth_result = sandbox.git.dangerously_authenticate(
                username,
                password,
            )
        except SandboxError as err:
            if is_unsupported_runtime_error(err):
                pytest.skip('envd does not support process stdin')
            raise
        assert_command_ok(
            'git authenticate',
            auth_result,
        )
        assert_command_ok(
            'git http version',
            sandbox.git.set_config(
                None, 'http.version', 'HTTP/1.1', global_config=True),
        )
        assert_git_network_ok(
            'git clone',
            lambda: (
                sandbox.commands.run('rm -rf {0}'.format(repo_path)),
                sandbox.git.clone(repo_url, repo_path, depth=1),
            )[1],
        )
        assert_command_ok(
            'configure user',
            sandbox.git.configure_user(
                repo_path,
                'Qiniu Python SDK',
                'qiniu-python-sdk@example.com',
            ),
        )
        assert_command_ok(
            'checkout branch',
            sandbox.git.checkout_branch(repo_path, branch, create=True),
        )
        sandbox.files.write(
            repo_path + '/python-sdk-integration.txt',
            'qiniu-python-sdk remote push {0}\n'.format(branch),
        )
        assert_command_ok('git add', sandbox.git.add(repo_path, all=True))
        assert_command_ok(
            'git commit',
            sandbox.git.commit(
                repo_path,
                'test: qiniu python sdk remote push',
            ),
        )
        assert_git_network_ok(
            'git push',
            lambda: sandbox.git.push(
                repo_path,
                'origin',
                'HEAD:refs/heads/{0}'.format(branch),
            ),
        )
    finally:
        if sandbox is not None:
            sandbox.kill()


def test_runtime_commands_filesystem_and_git_helpers():
    sandbox = None
    try:
        sandbox = create_integration_sandbox('runtime')

        stdout = []
        result = sandbox.commands.run(
            'printf runtime',
            on_stdout=stdout.append,
        )
        assert result.exit_code == 0
        assert result.stdout == 'runtime'
        assert stdout == ['runtime']

        sandbox.files.write_files([
            {'path': '/tmp/qiniu-python-sdk-a.txt', 'data': 'a'},
            {'path': '/tmp/qiniu-python-sdk-b.txt', 'data': 'b'},
        ])
        assert sandbox.files.read_text('/tmp/qiniu-python-sdk-a.txt') == 'a'
        assert sandbox.files.read_text('/tmp/qiniu-python-sdk-b.txt') == 'b'

        repo_path = '/tmp/qiniu-python-sdk-runtime-repo'
        sandbox.commands.run('rm -rf {0} && mkdir -p {0}'.format(repo_path))
        assert sandbox.git.init(repo_path).exit_code == 0
        assert sandbox.git.set_config(
            repo_path, 'user.name', 'Sandbox Demo').exit_code == 0
        assert sandbox.git.set_config(
            repo_path, 'user.email', 'sandbox-demo@example.com').exit_code == 0
        sandbox.files.write(repo_path + '/README.md', '# runtime\n')
        assert sandbox.git.add(repo_path, all=True).exit_code == 0
        assert sandbox.git.commit(
            repo_path, 'feat: runtime', allow_empty=True).exit_code == 0
        assert sandbox.git.create_branch(repo_path, 'feature').exit_code == 0
        assert sandbox.git.checkout_branch(repo_path, 'feature').exit_code == 0
        branches = sandbox.git.branches(repo_path)
        assert 'feature' in branches.branches
        assert branches.current_branch == 'feature'
        assert sandbox.git.get_config(repo_path, 'user.name').exit_code == 0
        assert sandbox.git.reset(repo_path, 'HEAD', mode='hard').exit_code == 0
        assert sandbox.git.restore(
            repo_path,
            paths=['README.md'],
        ).exit_code == 0
    finally:
        if sandbox is not None:
            sandbox.kill()


def test_filesystem_watch_dir_when_envd_supports_it():
    sandbox = None
    watcher = None
    try:
        sandbox = create_integration_sandbox('watch_dir')
        try:
            watcher = sandbox.files.watch_dir('/tmp')
        except SandboxError as err:
            if is_unsupported_runtime_error(err):
                pytest.skip('envd does not support filesystem watcher')
            raise

        sandbox.files.write('/tmp/qiniu-python-sdk-watch.txt', 'watch')
        events = []
        for _ in range(5):
            events = watcher.get_new_events()
            if events:
                break
            time.sleep(1)
        assert isinstance(events, list)
        assert all(hasattr(event, 'name') for event in events)
    finally:
        if watcher is not None:
            watcher.stop()
        if sandbox is not None:
            sandbox.kill()


def test_pty_when_envd_supports_it():
    sandbox = None
    try:
        sandbox = create_integration_sandbox('pty')
        try:
            handle = sandbox.pty.create(PtySize(rows=24, cols=80), timeout=30)
        except SandboxError as err:
            if is_unsupported_runtime_error(err):
                pytest.skip('envd does not support pty')
            raise

        try:
            sandbox.pty.send_stdin(handle.pid, 'echo qiniu-pty-ready\n')
            sandbox.pty.send_stdin(handle.pid, 'exit\n')
        except SandboxError as err:
            if is_unsupported_runtime_error(err):
                pytest.skip('envd can create pty but does not support input')
            raise
        result = handle.wait()
        assert 'qiniu-pty-ready' in result.stdout
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


@pytest.mark.parametrize('memory', [False, True])
def test_snapshot_lifecycle_and_connect_v2(memory):
    import uuid

    client = integration_client()
    source = None
    restored = None
    snapshot_id = None
    key = str(uuid.uuid4())
    name = 'python-sdk-it-{0}:v1'.format(key)
    try:
        source = Sandbox.create(
            os.getenv('QINIU_SANDBOX_TEMPLATE', 'base'), client=client,
            timeout=300, auto_pause=True, auto_pause_memory=memory,
            auto_resume={'enabled': False})
        source.files.write('/home/user/sdk-snapshot.txt', key)
        snapshot = source.create_snapshot(key, memory=memory, name=name)
        snapshot_id = snapshot['snapshotID']
        assert snapshot['names']
        replay = source.create_snapshot(key, memory=memory, name=name)
        assert replay['snapshotID'] == snapshot_id

        page = client.list_snapshots(
            sandbox_id=source.sandbox_id, name=name, limit=1)
        found = []
        while True:
            found.extend(item['snapshotID'] for item in page['items'])
            if not page['nextToken']:
                break
            page = client.list_snapshots(
                sandbox_id=source.sandbox_id, name=name, limit=1,
                next_token=page['nextToken'])
        assert snapshot_id in found
        tags = client.list_template_tags(snapshot_id)
        assert any(tag['tag'] == 'v1' for tag in tags)
        assert all(tag['buildID'] and tag['createdAt'] for tag in tags)

        restored = Sandbox.create(snapshot_id, client=client, timeout=300)
        restored.wait_for_ready()
        assert restored.files.read_text('/home/user/sdk-snapshot.txt') == key
        boot_id_command = 'cat /proc/sys/kernel/random/boot_id'
        before_boot = source.commands.run(boot_id_command).stdout.strip()
        assert before_boot
        source.pause(memory=memory)
        assert source.get_info()['state'] == 'paused'
        source.connect()
        source.wait_for_ready()
        assert source.files.read_text('/home/user/sdk-snapshot.txt') == key
        after_boot = source.commands.run(boot_id_command).stdout.strip()
        assert after_boot
        assert (before_boot == after_boot) is memory
    finally:
        try:
            if restored is not None:
                restored.kill()
        finally:
            try:
                if source is not None:
                    source.kill()
            finally:
                if snapshot_id:
                    client.delete_template(snapshot_id)


def test_template_disk_constraints():
    import uuid

    client = integration_client()
    template_id = None
    try:
        created = client.create_template(
            name='python-sdk-disk-{0}'.format(uuid.uuid4()),
            min_disk_mb=10240, min_free_disk_mb=0)
        template_id = created['templateID']
        assert created['buildID']
        client.start_template_build(
            template_id, created['buildID'],
            fromTemplate=os.getenv('QINIU_SANDBOX_TEMPLATE', 'base'))
        final = client.wait_for_build(
            template_id, created['buildID'], interval=3, timeout=300)
        assert final['status'] == 'ready'
    finally:
        if template_id:
            client.delete_template(template_id)


def test_http_body_injection_configuration():
    sandbox = None
    injection = {
        'type': 'http', 'base_url': 'https://api.example.com/v1/*',
        'if_body': {'model': 'sdk-test'}, 'body': {'api_key': 'sdk-test-secret'},
    }
    try:
        sandbox = Sandbox.create(
            os.getenv('QINIU_SANDBOX_TEMPLATE', 'base'),
            client=integration_client(), timeout=300, injections=[injection])
        rules = sandbox.get_injections()['injections']
        assert len(rules) == 1
        assert rules[0]['if_body'] == {'model': 'sdk-test'}
        assert rules[0].get('body') is None
        injection['if_body'] = {'model': 'updated-sdk-test'}
        sandbox.update_injections([injection])
        rules = sandbox.get_injections()['injections']
        assert rules[0]['if_body'] == {'model': 'updated-sdk-test'}
        assert rules[0].get('body') is None
        sandbox.update_injections([])
        assert sandbox.get_injections()['injections'] == []
    finally:
        if sandbox is not None:
            sandbox.kill()
