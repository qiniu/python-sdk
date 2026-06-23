# -*- coding: utf-8 -*-
import json

import pytest
import requests

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse

from qiniu.services.sandbox import (
    CommandExitError,
    DEFAULT_ENDPOINT,
    ENVD_PORT,
    GitAuthException,
    GitBranches,
    GitStatus,
    Git,
    InvalidArgumentException,
    KodoResource,
    ReadyCmd,
    Sandbox,
    SandboxClient,
    SandboxError,
    SandboxPaginator,
    Template,
    wait_for_file,
    wait_for_port,
    wait_for_process,
    wait_for_timeout,
    wait_for_url,
)
from qiniu.services.sandbox.util import encode_path, file_signature


class DummyResponse(object):
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.content = b'' if body is None else json.dumps(
            body).encode('utf-8')
        self.text = self.content.decode('utf-8')
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        if not self.content:
            return None
        return json.loads(self.content.decode('utf-8'))


class ErrorResponse(object):
    def __init__(self, status_code=502):
        self.status_code = status_code
        self.content = b''
        self.text = ''
        self.headers = {}

    def json(self):
        return None


class RecordingSession(requests.Session):
    def __init__(self, responses=None):
        super(RecordingSession, self).__init__()
        self.responses = list(responses or [DummyResponse(body={})])
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return DummyResponse(body={})

    def get(self, url, **kwargs):
        self.requests.append(type('Request', (object,), {
            'method': 'GET',
            'url': url,
            'kwargs': kwargs,
        })())
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return DummyResponse(body={})


def body_of(request):
    if request.body is None:
        return None
    if isinstance(request.body, bytes):
        return json.loads(request.body.decode('utf-8'))
    return json.loads(request.body)


def test_client_uses_default_endpoint_and_api_key_headers():
    session = RecordingSession([DummyResponse(201, {
        'sandboxID': 'sbx123',
        'templateID': 'base',
        'domain': 'example.test',
        'envdAccessToken': 'envd-token',
    })])
    client = SandboxClient(api_key='api-key', session=session)

    info = client.create_sandbox(template='base', timeout=60, envs={'A': 'B'})

    assert info['sandboxID'] == 'sbx123'
    req = session.requests[0]
    assert req.method == 'POST'
    assert req.url == DEFAULT_ENDPOINT + '/sandboxes'
    assert req.headers['X-API-Key'] == 'api-key'
    assert req.headers['Authorization'] == 'Bearer api-key'
    assert body_of(req) == {
        'templateID': 'base',
        'timeout': 60,
        'envVars': {'A': 'B'},
    }


def test_util_helpers_encode_unicode_values_safely():
    assert encode_path(u'目录/文件.txt')
    assert file_signature(
        u'/tmp/文件.txt',
        'read',
        u'用户',
        u'token',
        1893456000,
    ).startswith('v1_')


def test_create_with_kodo_resource_requires_qiniu_credentials():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.create_sandbox(
            resources=[
                KodoResource(
                    bucket='bucket',
                    mount_path='/mnt/bucket')])

    assert 'Qiniu AK/SK' in str(err.value)


def test_create_with_kodo_resource_uses_qiniu_signature():
    session = RecordingSession(
        [DummyResponse(201, {'sandboxID': 'sbx123', 'templateID': 'base'})])
    client = SandboxClient(access_key='ak', secret_key='sk', session=session)

    client.create_sandbox(
        resources=[
            KodoResource(
                bucket='bucket',
                mount_path='/mnt/bucket')])

    req = session.requests[0]
    assert req.headers['Authorization'].startswith('Qiniu ak:')
    assert 'X-Qiniu-Date' in req.headers
    assert body_of(req)['resources'] == [{
        'type': 'kodo',
        'bucket': 'bucket',
        'mount_path': '/mnt/bucket',
    }]


def test_create_with_saved_injection_rule_requires_qiniu_credentials():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.create_sandbox(injections=[{
            'type': 'id',
            'ruleID': 'rule-1',
        }])

    assert 'Qiniu AK/SK' in str(err.value)


def test_create_with_saved_injection_rule_uses_qiniu_signature():
    session = RecordingSession(
        [DummyResponse(201, {'sandboxID': 'sbx123', 'templateID': 'base'})])
    client = SandboxClient(access_key='ak', secret_key='sk', session=session)

    client.create_sandbox(injections=[{
        'type': 'id',
        'ruleId': 'rule-1',
    }])

    req = session.requests[0]
    assert req.headers['Authorization'].startswith('Qiniu ak:')
    assert body_of(req)['injections'] == [{
        'type': 'id',
        'ruleID': 'rule-1',
    }]


def test_sandbox_create_signature_matches_e2b_style():
    session = RecordingSession([
        DummyResponse(201, {
            'sandboxID': 'sbx123',
            'templateID': 'python',
            'domain': 'example.test',
            'envdAccessToken': 'envd-token',
        })
    ])
    client = SandboxClient(api_key='api-key', session=session)

    sandbox = Sandbox.create(
        'python',
        timeout=120,
        metadata={'app': 'tests'},
        envs={'HELLO': 'world'},
        client=client,
    )

    assert sandbox.sandbox_id == 'sbx123'
    assert sandbox.sandboxID == 'sbx123'
    assert sandbox.template_id == 'python'
    assert sandbox.files is sandbox.filesystem
    assert sandbox.commands.sandbox is sandbox
    assert body_of(session.requests[0])['templateID'] == 'python'


def test_client_uses_default_http_timeout():
    client = SandboxClient(api_key='api-key', session=RecordingSession())
    custom = SandboxClient(
        api_key='api-key',
        session=RecordingSession(),
        timeout=12,
    )

    assert client.timeout == 30
    assert custom.timeout == 12


def test_client_wraps_request_exceptions_in_sandbox_error():
    client = SandboxClient(
        api_key='api-key',
        session=RecordingSession([requests.Timeout('timed out')]))

    with pytest.raises(SandboxError) as err:
        client.list_sandboxes()

    assert 'Sandbox API request failed' in str(err.value)
    assert 'timed out' in str(err.value)


def test_sandbox_instance_lifecycle_methods_call_control_plane():
    session = RecordingSession([
        DummyResponse(204, None),
        DummyResponse(204, None),
        DummyResponse(200, {
            'sandboxID': 'sbx123',
            'templateID': 'base',
            'envdAccessToken': 'envd-token',
        }),
    ])
    client = SandboxClient(api_key='api-key', session=session)
    sandbox = Sandbox(
        client=client,
        info={
            'sandboxID': 'sbx123',
            'templateID': 'base'})

    assert sandbox.kill() is None
    assert sandbox.set_timeout(30) is None
    sandbox.connect(timeout=45)

    assert [
        req.method for req in session.requests] == [
        'DELETE',
        'POST',
        'POST']
    assert session.requests[0].url.endswith('/sandboxes/sbx123')
    assert session.requests[1].url.endswith('/sandboxes/sbx123/timeout')
    assert body_of(session.requests[1]) == {'timeout': 30}
    assert session.requests[2].url.endswith('/sandboxes/sbx123/connect')
    assert body_of(session.requests[2]) == {'timeout': 45}


def test_connect_sandbox_uses_timeout_body_only():
    session = RecordingSession([DummyResponse(200, {'sandboxID': 'sbx123'})])
    client = SandboxClient(api_key='api-key', session=session)

    client.connect_sandbox('sbx123', timeout=9)

    assert body_of(session.requests[0]) == {'timeout': 9}


def test_delete_template_requires_template_id():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.delete_template(None)

    assert 'template_id is required' in str(err.value)


def test_sandbox_envd_and_file_urls_are_signed_when_token_is_available():
    sandbox = Sandbox(info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
        'envdAccessToken': 'token',
    })

    assert sandbox.get_host(ENVD_PORT) == '49983-sbx123.example.test'
    assert sandbox.envd_url() == 'https://49983-sbx123.example.test'

    url = sandbox.download_url(
        '/tmp/hello.txt',
        signature_expiration=1893456000)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == 'https'
    assert parsed.netloc == '49983-sbx123.example.test'
    assert parsed.path == '/files'
    assert query['path'] == ['/tmp/hello.txt']
    assert query['username'] == ['user']
    assert query['signature_expiration'] == ['1893456000']
    assert query['signature'][0]


def test_file_url_accepts_none_signature_expiration():
    sandbox = Sandbox(info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
        'envdAccessToken': 'token',
    })

    url = sandbox.download_url('/tmp/hello.txt', signatureExpiration=None)
    query = parse_qs(urlparse(url).query)

    assert query['signature'][0]
    assert 'signature_expiration' not in query


def test_wait_for_ready_passes_request_timeout_to_health_check():
    session = RecordingSession([DummyResponse(200, {})])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
    })

    sandbox.wait_for_ready(timeout=10, interval=2)

    assert session.requests[0].url == sandbox.envd_url() + '/health'
    assert session.requests[0].kwargs['timeout'] == 5


def test_wait_for_ready_caps_request_timeout_to_remaining_timeout():
    session = RecordingSession([DummyResponse(200, {})])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
    })

    sandbox.wait_for_ready(timeout=3, interval=2)

    assert session.requests[0].kwargs['timeout'] <= 3


def test_wait_for_ready_ignores_startup_request_errors_until_ready():
    session = RecordingSession([
        requests.exceptions.ConnectionError('envd is starting'),
        DummyResponse(200, {}),
    ])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
    })

    sandbox.wait_for_ready(timeout=10, interval=0)

    assert len(session.requests) == 2


def test_wait_for_ready_raises_sandbox_error_on_timeout():
    session = RecordingSession([
        requests.exceptions.ConnectionError('envd is starting'),
    ])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
    })

    with pytest.raises(SandboxError):
        sandbox.wait_for_ready(timeout=0, interval=0)


def test_update_info_refreshes_traffic_access_token():
    sandbox = Sandbox(info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
        'trafficAccessToken': 'old-token',
    })

    sandbox.update_info({'trafficAccessToken': 'new-token'})

    assert sandbox.traffic_access_token == 'new-token'
    assert sandbox.trafficAccessToken == 'new-token'


class RecordingSandboxListClient(object):
    def __init__(self):
        self.calls = []

    def list_sandboxes_v2(self, **opts):
        self.calls.append(opts)
        if len(self.calls) == 1:
            return {'items': [], 'nextToken': 'next-page'}
        return {'items': []}


def test_sandbox_paginator_does_not_reuse_initial_next_token():
    client = RecordingSandboxListClient()
    paginator = SandboxPaginator(client=client, next_token='saved-page')

    paginator.next_items()
    paginator.next_items()

    assert client.calls[0]['nextToken'] == 'saved-page'
    assert client.calls[1]['nextToken'] == 'next-page'


def test_is_running_matches_e2b_health_check_semantics():
    running_session = RecordingSession([DummyResponse(200, {})])
    running = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=running_session,
    ), info={'sandboxID': 'sbx123', 'domain': 'example.test'})

    stopped_session = RecordingSession([ErrorResponse(502)])
    stopped = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=stopped_session,
    ), info={'sandboxID': 'sbx123', 'domain': 'example.test'})

    assert running.is_running(request_timeout=3) is True
    assert running_session.requests[0].kwargs['timeout'] == 3
    assert stopped.is_running() is False


def test_is_running_returns_false_for_envd_request_errors():
    session = RecordingSession([requests.Timeout('timed out')])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={'sandboxID': 'sbx123', 'domain': 'example.test'})

    assert sandbox.is_running(request_timeout=1) is False
    assert session.requests[0].kwargs['timeout'] == 1


def test_get_sandboxes_metrics_serializes_ids_as_comma_string():
    session = RecordingSession([DummyResponse(200, {'metrics': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.get_sandboxes_metrics(['sbx1', 'sbx2'])

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['sandbox_ids'] == ['sbx1,sbx2']


def test_get_sandboxes_metrics_rejects_empty_dict_values():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError):
        client.get_sandboxes_metrics({})
    with pytest.raises(SandboxError):
        client.get_sandboxes_metrics({'sandboxIDs': None})


def test_template_builder_outputs_build_config():
    template = (
        Template()
        .from_image('python:3.11')
        .run_cmd('pip install qiniu')
        .copy('/local/app.py', '/app/app.py')
        .set_env('PYTHONUNBUFFERED', '1')
        .set_start_cmd('python /app/app.py')
    )

    assert template.to_dict() == {
        'fromImage': 'python:3.11',
        'steps': [
            {'type': 'RUN', 'args': ['pip install qiniu']},
            {'type': 'COPY', 'args': ['/local/app.py', '/app/app.py']},
            {'type': 'ENV', 'args': ['PYTHONUNBUFFERED', '1']},
        ],
        'startCmd': 'python /app/app.py',
    }


def test_template_ready_cmd_helpers_align_with_e2b():
    ready = wait_for_port(8000)
    assert isinstance(ready, ReadyCmd)
    assert ready.get_cmd() == 'ss -tuln | grep :8000'
    assert wait_for_url(
        'http://localhost:3000/health',
        status_code=204,
    ).get_cmd() == (
        '[ "$(curl -s -o /dev/null -w "%{http_code}" '
        'http://localhost:3000/health)" = "204" ]'
    )
    assert wait_for_process('nginx').get_cmd() == 'pgrep nginx > /dev/null'
    assert wait_for_file('/tmp/ready').get_cmd() == '[ -f /tmp/ready ]'
    assert wait_for_timeout(500).get_cmd() == 'sleep 1'

    template = (
        Template()
        .from_image('python:3.11')
        .set_start_cmd('python app.py', wait_for_port(8000))
    )

    assert template.to_dict()['startCmd'] == 'python app.py'
    assert template.to_dict()['readyCmd'] == 'ss -tuln | grep :8000'


def test_template_ready_cmd_helpers_quote_shell_inputs():
    assert wait_for_url(
        'http://localhost:3000/health; touch /tmp/pwn',
        status_code='204',
    ).get_cmd() == (
        '[ "$(curl -s -o /dev/null -w "%{http_code}" '
        '\'http://localhost:3000/health; touch /tmp/pwn\')" = "204" ]'
    )
    assert wait_for_process('nginx; touch /tmp/pwn').get_cmd() == (
        "pgrep 'nginx; touch /tmp/pwn' > /dev/null"
    )
    assert wait_for_file('/tmp/ready; touch /tmp/pwn').get_cmd() == (
        "[ -f '/tmp/ready; touch /tmp/pwn' ]"
    )
    with pytest.raises(ValueError):
        wait_for_port('8000; touch /tmp/pwn')
    with pytest.raises(ValueError):
        wait_for_url('http://localhost:3000', status_code='200; true')


class RecordingCommands(object):
    def __init__(self):
        self.calls = []
        self.results = []

    def run(self, cmd, **opts):
        self.calls.append((cmd, opts))
        result = self.results.pop(0) if self.results else type(
            'Result', (object,), {
                'pid': 12,
                'exit_code': 0,
                'stdout': 'origin https://github.com/qiniu/repo.git\n',
                'stderr': '',
                'error': '',
            })()
        if result.exit_code and opts.get('throw_on_error'):
            from qiniu.services.sandbox import CommandExitError
            raise CommandExitError(result)
        if opts.get('background'):
            return type('Handle', (object,), {
                'pid': getattr(result, 'pid', 12),
                'wait': lambda self: result,
            })()
        return result

    def send_stdin(self, pid, data):
        self.calls.append(('send_stdin', {'pid': pid, 'data': data}))
        return None

    def close_stdin(self, pid):
        self.calls.append(('close_stdin', {'pid': pid}))
        return None


def test_git_helpers_align_with_e2b_method_names():
    commands = RecordingCommands()
    git = Git(commands)

    git.remote_add('/repo', 'origin', 'https://github.com/qiniu/repo.git')
    git.remote_get('/repo', 'origin')
    git.branches('/repo')
    git.create_branch('/repo', 'feature')
    git.checkout_branch('/repo', 'main')
    git.delete_branch('/repo', 'old')
    git.reset('/repo', 'HEAD~1', mode='hard')
    git.restore('/repo', paths=['a.txt', 'b.txt'])
    git.set_config('/repo', 'user.name', 'tester')
    git.get_config('/repo', 'user.name')

    assert commands.calls[0][0] == (
        'git remote add origin https://github.com/qiniu/repo.git')
    assert commands.calls[1][0] == 'git remote get-url origin'
    assert commands.calls[2][0] == (
        "git branch '--format=%(refname:short)\t%(HEAD)'")
    assert commands.calls[3][0] == 'git checkout -b feature'
    assert commands.calls[4][0] == 'git checkout main'
    assert commands.calls[5][0] == 'git branch -D old'
    assert commands.calls[6][0] == "git reset --hard 'HEAD~1'"
    assert commands.calls[7][0] == 'git restore a.txt b.txt'
    assert commands.calls[8][0] == 'git config user.name tester'
    assert commands.calls[9][0] == 'git config --get user.name'


def test_git_remote_add_supports_overwrite_and_fetch_options():
    commands = RecordingCommands()
    git = Git(commands)

    git.remote_add(
        '/repo',
        'origin',
        'https://github.com/qiniu/repo.git',
        overwrite=True,
        fetch=True,
    )

    assert commands.calls[0][0] == 'git remote remove origin'
    assert commands.calls[1][0] == (
        'git remote add origin https://github.com/qiniu/repo.git')
    assert commands.calls[2][0] == 'git fetch origin'


def test_git_add_and_restore_accept_single_string_path():
    commands = RecordingCommands()
    git = Git(commands)

    git.add('/repo', files='README.md')
    git.restore('/repo', paths='README.md')
    git.restore('/repo', files='setup.py')

    assert commands.calls[0][0] == 'git add README.md'
    assert commands.calls[1][0] == 'git restore README.md'
    assert commands.calls[2][0] == 'git restore setup.py'


def test_git_reset_rejects_unsupported_mode():
    commands = RecordingCommands()
    git = Git(commands)

    with pytest.raises(InvalidArgumentException):
        git.reset('/repo', 'HEAD', mode='hard; touch /tmp/pwn')

    assert commands.calls == []


def test_git_dangerously_authenticate_aligns_with_e2b():
    commands = RecordingCommands()
    git = Git(commands)

    git.dangerously_authenticate(
        username='git-user',
        password='secret-token',
        host='github.com',
        protocol='https',
    )

    assert commands.calls[0][0] == (
        'git config --global credential.helper store')
    assert commands.calls[1][0] == 'git credential approve'
    assert commands.calls[1][1]['stdin'] is True
    assert commands.calls[1][1]['background'] is True
    assert commands.calls[2] == ('send_stdin', {
        'pid': 12,
        'data': (
            'protocol=https\nhost=github.com\n'
            'username=git-user\npassword=secret-token\n\n'
        ),
    })
    assert commands.calls[3] == ('close_stdin', {'pid': 12})


def test_git_dangerously_authenticate_uses_temp_file_with_real_sandbox():
    class FakeFiles(object):
        def __init__(self):
            self.writes = []
            self.removes = []

        def write(self, path, data, **opts):
            self.writes.append((path, data, opts))
            return None

        def remove(self, path, **opts):
            self.removes.append((path, opts))
            return None

    commands = RecordingCommands()
    files = FakeFiles()
    commands.sandbox = type('Sandbox', (object,), {'files': files})()
    git = Git(commands)

    git.dangerously_authenticate(
        username='git-user',
        password='secret-%-token',
        host='github.com',
        protocol='https',
    )

    assert files.writes[0][1] == (
        'protocol=https\nhost=github.com\n'
        'username=git-user\npassword=secret-%-token\n\n'
    )
    assert files.writes[0][2] == {}
    assert commands.calls[1][0].startswith('chmod 600 /tmp/')
    assert commands.calls[2][0].startswith('trap "rm -f /tmp/')
    assert 'git credential approve' in commands.calls[2][0]
    assert 'secret-%-token' not in commands.calls[2][0]
    assert files.removes == [(files.writes[0][0], {})]


def test_git_dangerously_authenticate_removes_temp_file_on_chmod_failure():
    class FakeFiles(object):
        def __init__(self):
            self.writes = []
            self.removes = []

        def write(self, path, data, **opts):
            self.writes.append((path, data, opts))
            return None

        def remove(self, path, **opts):
            self.removes.append((path, opts))
            return None

    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'pid': 12,
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'pid': 12,
            'exit_code': 1,
            'stdout': '',
            'stderr': 'chmod failed',
            'error': 'chmod failed',
        })(),
    ]
    files = FakeFiles()
    commands.sandbox = type('Sandbox', (object,), {'files': files})()
    git = Git(commands)

    result = git.dangerously_authenticate(
        username='git-user',
        password='secret-token',
    )

    assert result.exit_code == 1
    assert files.removes == [(files.writes[0][0], {})]


def test_git_status_and_branches_return_structured_e2b_types():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': (
                '## main...origin/main [ahead 2, behind 1]\n'
                ' M changed.txt\n'
                'A  staged.txt\n'
                '?? new.txt\n'
            ),
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'main\t*\nfeature\t\n',
            'stderr': '',
            'error': '',
        })(),
    ]
    git = Git(commands)

    status = git.status('/repo')
    branches = git.branches('/repo')

    assert isinstance(status, GitStatus)
    assert status.current_branch == 'main'
    assert status.upstream == 'origin/main'
    assert status.ahead == 2
    assert status.behind == 1
    assert status.has_changes is True
    assert status.has_staged is True
    assert status.has_untracked is True
    assert status.file_status[0].name == 'changed.txt'
    assert status.file_status[0].status == 'modified'
    assert isinstance(branches, GitBranches)
    assert branches.branches == ['main', 'feature']
    assert branches.current_branch == 'main'


def test_git_push_maps_auth_failure_to_e2b_exception():
    commands = RecordingCommands()
    commands.results = [type('Result', (object,), {
        'exit_code': 128,
        'stdout': '',
        'stderr': 'fatal: Authentication failed',
        'error': '',
    })()]
    git = Git(commands)

    with pytest.raises(GitAuthException):
        git.push('/repo')


def test_git_credential_remote_requires_existing_remote():
    commands = RecordingCommands()
    commands.results = [type('Result', (object,), {
        'exit_code': 0,
        'stdout': '',
        'stderr': '',
        'error': '',
    })()]
    git = Git(commands)

    with pytest.raises(InvalidArgumentException) as err:
        git.push('/repo', username='git-user', password='secret')

    assert 'No remotes found' in str(err.value)


def test_git_push_maps_known_errors_before_throw_on_error():
    commands = RecordingCommands()
    commands.results = [type('Result', (object,), {
        'exit_code': 128,
        'stdout': '',
        'stderr': 'fatal: Authentication failed',
        'error': '',
    })()]
    git = Git(commands)

    with pytest.raises(GitAuthException):
        git.push('/repo', throw_on_error=True)


def test_git_push_respects_throw_on_error_for_unknown_errors():
    commands = RecordingCommands()
    commands.results = [type('Result', (object,), {
        'exit_code': 1,
        'stdout': '',
        'stderr': 'unexpected failure',
        'error': '',
    })()]
    git = Git(commands)

    with pytest.raises(CommandExitError):
        git.push('/repo', throw_on_error=True)


def test_git_push_with_credentials_sets_remote_url_temporarily():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'https://old:old-token@github.com/qiniu/repo.git\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
    ]
    git = Git(commands)

    git.push(
        '/repo',
        remote='origin',
        branch='main',
        username='git:user',
        password='secret:%@token',
        request_timeout=7,
    )

    assert commands.calls[0][0] == 'git remote get-url origin'
    assert commands.calls[1][0] == (
        'git remote set-url origin '
        'https://git%3Auser:secret%3A%25%40token@github.com/qiniu/repo.git'
    )
    assert commands.calls[2][0] == 'git push --set-upstream origin main'
    assert commands.calls[3][0] == (
        'git remote set-url origin '
        'https://old:old-token@github.com/qiniu/repo.git'
    )
    assert commands.calls[2][1]['request_timeout'] == 7


def test_git_pull_with_credentials_resolves_single_remote():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'origin\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'https://github.com/qiniu/repo.git\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
    ]
    git = Git(commands)

    git.pull(
        '/repo',
        branch='main',
        username='git-user',
        password='secret-token',
    )

    assert commands.calls[0][0] == 'git remote'
    assert commands.calls[2][0] == (
        'git remote set-url origin '
        'https://git-user:secret-token@github.com/qiniu/repo.git'
    )
    assert commands.calls[3][0] == 'git pull origin main'
    assert commands.calls[4][0] == (
        'git remote set-url origin https://github.com/qiniu/repo.git'
    )


def test_git_push_with_credentials_restores_remote_on_auth_failure():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'https://github.com/qiniu/repo.git\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 128,
            'stdout': '',
            'stderr': 'fatal: Authentication failed',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
    ]
    git = Git(commands)

    with pytest.raises(GitAuthException):
        git.push(
            '/repo',
            remote='origin',
            username='git-user',
            password='bad-token',
        )

    assert commands.calls[-1][0] == (
        'git remote set-url origin https://github.com/qiniu/repo.git'
    )


def test_git_push_reports_restore_failure_after_credentials_are_injected():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'https://github.com/qiniu/repo.git\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 128,
            'stdout': '',
            'stderr': 'fatal: Authentication failed',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 1,
            'stdout': '',
            'stderr': 'config locked',
            'error': '',
        })(),
    ]
    git = Git(commands)

    with pytest.raises(SandboxError) as err:
        git.push(
            '/repo',
            remote='origin',
            username='git-user',
            password='bad-token',
        )

    assert 'Credentials may be leaked' in str(err.value)
    assert 'config locked' in str(err.value)


def test_git_push_reports_restore_failure_after_operation_exception():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'https://github.com/qiniu/repo.git\n',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': '',
            'stderr': '',
            'error': '',
        })(),
        type('Result', (object,), {
            'exit_code': 1,
            'stdout': '',
            'stderr': 'config locked',
            'error': '',
        })(),
    ]
    git = Git(commands)

    with pytest.raises(SandboxError) as err:
        git._with_remote_credentials(
            '/repo',
            'origin',
            'git-user',
            'bad-token',
            lambda: (_ for _ in ()).throw(SandboxError('rpc timed out')),
        )

    assert 'Credentials may be leaked' in str(err.value)
    assert 'config locked' in str(err.value)
    assert 'rpc timed out' in str(err.value)


def test_git_helpers_accept_e2b_style_signatures():
    commands = RecordingCommands()
    git = Git(commands)

    git.create_branch('/repo', 'feature')
    git.commit(
        '/repo',
        'feat: demo',
        author_name='Demo User',
        author_email='demo@example.com',
        allow_empty=True,
    )
    git.set_config('user.name', 'Demo User', scope='local', path='/repo')
    git.get_config('user.name', scope='local', path='/repo')

    assert commands.calls[0][0] == 'git checkout -b feature'
    assert commands.calls[1][0] == (
        "git -c 'user.name=Demo User' -c user.email=demo@example.com "
        "commit -m 'feat: demo' --allow-empty"
    )
    assert commands.calls[2][0] == "git config --local user.name 'Demo User'"
    assert commands.calls[2][1]['cwd'] == '/repo'
    assert commands.calls[3][0] == 'git config --local --get user.name'
    assert commands.calls[3][1]['cwd'] == '/repo'
