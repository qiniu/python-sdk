# -*- coding: utf-8 -*-
import json

import pytest
import requests

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse

from qiniu.services.sandbox import (
    DEFAULT_ENDPOINT,
    ENVD_PORT,
    Git,
    KodoResource,
    Sandbox,
    SandboxClient,
    SandboxError,
    Template,
)


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


class RecordingSession(requests.Session):
    def __init__(self, responses=None):
        super(RecordingSession, self).__init__()
        self.responses = list(responses or [DummyResponse(body={})])
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        if self.responses:
            return self.responses.pop(0)
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


class RecordingCommands(object):
    def __init__(self):
        self.calls = []

    def run(self, cmd, **opts):
        self.calls.append((cmd, opts))
        return type('Result', (object,), {
            'exit_code': 0,
            'stdout': 'origin https://github.com/qiniu/repo.git\n',
            'stderr': '',
        })()


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
    assert commands.calls[2][0] == 'git branch --list'
    assert commands.calls[3][0] == 'git branch feature'
    assert commands.calls[4][0] == 'git checkout main'
    assert commands.calls[5][0] == 'git branch -D old'
    assert commands.calls[6][0] == "git reset --hard 'HEAD~1'"
    assert commands.calls[7][0] == 'git restore a.txt b.txt'
    assert commands.calls[8][0] == 'git config user.name tester'
    assert commands.calls[9][0] == 'git config --get user.name'


def test_git_dangerously_authenticate_aligns_with_e2b():
    commands = RecordingCommands()
    git = Git(commands)

    git.dangerously_authenticate(
        username='git-user',
        password='secret-token',
        host='github.com',
        protocol='https',
    )

    assert commands.calls[0][0] == 'git config --global credential.helper store'
    assert commands.calls[1][0] == (
        "printf 'protocol=https\nhost=github.com\n"
        "username=git-user\npassword=secret-token\n\n' | "
        'git credential approve'
    )
