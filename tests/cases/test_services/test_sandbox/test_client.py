# -*- coding: utf-8 -*-
import gc
import json
import threading

import pytest
import requests
import qiniu.services.sandbox.client as sandbox_client_module
import qiniu.services.sandbox.sandbox as sandbox_module

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse

try:
    from socketserver import StreamRequestHandler, TCPServer
except ImportError:
    from SocketServer import StreamRequestHandler, TCPServer

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


def test_create_template_maps_minimum_disk_sizes_to_api_fields():
    session = RecordingSession([DummyResponse(202, {
        'templateID': 'tpl123',
        'buildID': 'build123',
    })])
    client = SandboxClient(api_key='api-key', session=session)

    client.create_template(name='disk-size-test', min_disk_mb=15360, min_free_disk_mb=5120)

    req = session.requests[0]
    assert req.method == 'POST'
    assert req.url == DEFAULT_ENDPOINT + '/v3/templates'
    assert body_of(req) == {
        'name': 'disk-size-test',
        'minDiskMb': 15360,
        'minFreeDiskMb': 5120,
    }


def test_sandbox_resource_apis_list_and_update_git_token():
    session = RecordingSession([
        DummyResponse(200, {'resources': [{
            'type': 'github_repository',
            'resource_id': 'res123',
            'url': 'https://github.com/qiniu/python-sdk.git',
            'mount_path': '/workspace/repo',
        }]}),
        DummyResponse(204),
    ])
    client = SandboxClient(api_key='api-key', session=session)

    resources = client.get_sandbox_resources('sbx/123')
    client.update_git_repository_resource_token(
        'sbx/123', 'res/123', 'new-token')

    assert resources['resources'][0]['resource_id'] == 'res123'
    assert session.requests[0].method == 'GET'
    assert session.requests[0].url == (
        DEFAULT_ENDPOINT + '/sandboxes/sbx%2F123/resources')
    assert session.requests[1].method == 'PATCH'
    assert session.requests[1].url == (
        DEFAULT_ENDPOINT + '/sandboxes/sbx%2F123/resources/res%2F123')
    assert body_of(session.requests[1]) == {
        'authorization_token': 'new-token',
    }


@pytest.mark.parametrize('status_code', [408, 500])
def test_create_sandbox_retries_retryable_status_and_reuses_idempotency_key(
        monkeypatch, status_code):
    session = RecordingSession([
        ErrorResponse(status_code),
        DummyResponse(201, {'sandboxID': 'sbx123'}),
    ])
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    client = SandboxClient(
        api_key='api-key', session=session, max_retries=1)

    result = client.create_sandbox(
        template='base', idempotency_key='retry-key')

    assert result['sandboxID'] == 'sbx123'
    assert len(session.requests) == 2
    assert [request.headers['Idempotency-Key'] for request in session.requests] == [
        'retry-key', 'retry-key']


@pytest.mark.parametrize(
    'error_type', [requests.ConnectionError, requests.exceptions.SSLError])
def test_create_sandbox_retries_transport_error_and_reuses_idempotency_key(
        monkeypatch, error_type):
    session = RecordingSession([
        error_type('[Errno 101] Network is unreachable'),
        DummyResponse(201, {'sandboxID': 'sbx123'}),
    ])
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    client = SandboxClient(
        api_key='api-key', session=session, max_retries=1)

    result = client.create_sandbox(
        template='base', idempotency_key='retry-key')

    assert result['sandboxID'] == 'sbx123'
    assert len(session.requests) == 2
    assert [request.headers['Idempotency-Key'] for request in session.requests] == [
        'retry-key', 'retry-key']


@pytest.mark.parametrize('max_retries', [-1, '1', 1.5, True])
def test_sandbox_client_rejects_invalid_max_retries(max_retries):
    with pytest.raises(SandboxError, match='max_retries'):
        SandboxClient(
            api_key='api-key', session=RecordingSession(),
            max_retries=max_retries)


@pytest.mark.parametrize('max_retries', ['-1', 'invalid'])
def test_sandbox_client_rejects_invalid_retry_environment(
        monkeypatch, max_retries):
    monkeypatch.setenv('SANDBOX_RETRY_MAX', max_retries)

    with pytest.raises(SandboxError, match='SANDBOX_RETRY_MAX'):
        SandboxClient(api_key='api-key', session=RecordingSession())


def test_sandbox_client_allows_zero_max_retries():
    client = SandboxClient(
        api_key='api-key', session=RecordingSession(), max_retries=0)

    assert client.max_retries == 0


def test_sandbox_create_forwards_max_retries(monkeypatch):
    created_clients = []

    class CapturingClient(object):
        def __init__(self, **opts):
            self.max_retries = opts.get('max_retries')
            created_clients.append(self)

        def create_sandbox(self, *args, **opts):
            return {'sandboxID': 'sbx123'}

        def get_sandbox(self, sandbox_id):
            return {'sandboxID': sandbox_id, 'envdAccessToken': 'token'}

    monkeypatch.setattr(sandbox_module, 'SandboxClient', CapturingClient)

    sandbox = Sandbox.create('base', max_retries=0)

    assert sandbox.sandbox_id == 'sbx123'
    assert created_clients[0].max_retries == 0


def test_create_sandbox_rejects_conflicting_option_aliases():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as env_err:
        client.create_sandbox(envs={'A': 'B'}, envVars={'A': 'C'})
    with pytest.raises(SandboxError) as network_err:
        client.create_sandbox(
            allow_internet_access=True,
            allowInternetAccess=False,
        )

    assert 'envs, envVars' in str(env_err.value)
    assert 'allow_internet_access, allowInternetAccess' in str(
        network_err.value)


def test_create_sandbox_uses_api_field_names_and_preserves_lifecycle():
    session = RecordingSession([DummyResponse(201, {'sandboxID': 'sbx123'})])
    client = SandboxClient(api_key='api-key', session=session)

    client.create_sandbox(
        template='base',
        allow_internet_access=False,
        lifecycle={
            'onTimeout': 'pause',
            'customRule': {'action': 'notify'},
        },
    )

    assert body_of(session.requests[0]) == {
        'templateID': 'base',
        'allowInternetAccess': False,
        'lifecycle': {
            'onTimeout': 'pause',
            'customRule': {'action': 'notify'},
        },
        'autoPause': True,
    }


def test_client_reads_documented_api_key_env_fallbacks(monkeypatch):
    monkeypatch.delenv('QINIU_SANDBOX_API_KEY', raising=False)
    monkeypatch.delenv('QINIU_API_KEY', raising=False)
    monkeypatch.delenv('E2B_API_KEY', raising=False)

    monkeypatch.setenv('QINIU_API_KEY', 'qiniu-api-key')
    assert SandboxClient(session=RecordingSession()).api_key == 'qiniu-api-key'

    monkeypatch.delenv('QINIU_API_KEY')
    monkeypatch.setenv('E2B_API_KEY', 'e2b-api-key')
    assert SandboxClient(session=RecordingSession()).api_key == 'e2b-api-key'

    monkeypatch.setenv('QINIU_SANDBOX_API_KEY', 'sandbox-api-key')
    assert SandboxClient(session=RecordingSession()).api_key == (
        'sandbox-api-key')


def test_client_reads_qiniu_mac_credentials_from_env(monkeypatch):
    monkeypatch.delenv('QINIU_SANDBOX_ACCESS_KEY', raising=False)
    monkeypatch.delenv('QINIU_SANDBOX_SECRET_KEY', raising=False)
    monkeypatch.setenv('QINIU_SANDBOX_ACCESS_KEY', 'ak')
    monkeypatch.setenv('QINIU_SANDBOX_SECRET_KEY', 'sk')

    client = SandboxClient(session=RecordingSession())

    assert client.mac is not None


def test_util_helpers_encode_unicode_values_safely():
    assert encode_path(u'目录/文件.txt')
    assert file_signature(
        u'/tmp/文件.txt',
        'read',
        u'用户',
        u'token',
        1893456000,
    ).startswith('v1_')


def test_create_with_kodo_resource_requires_qiniu_credentials(monkeypatch):
    monkeypatch.delenv('QINIU_SANDBOX_ACCESS_KEY', raising=False)
    monkeypatch.delenv('QINIU_SANDBOX_SECRET_KEY', raising=False)
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
    client = SandboxClient(
        api_key='api-key',
        access_key='ak',
        secret_key='sk',
        session=session,
    )

    client.create_sandbox(
        resources=[
            KodoResource(
                bucket='bucket',
                mount_path='/mnt/bucket')])

    req = session.requests[0]
    assert req.headers['X-API-Key'] == 'api-key'
    assert req.headers['Authorization'].startswith('Qiniu ak:')
    assert 'X-Qiniu-Date' in req.headers
    assert body_of(req)['resources'] == [{
        'type': 'kodo',
        'bucket': 'bucket',
        'mount_path': '/mnt/bucket',
    }]


def test_create_with_inline_kodo_credentials_uses_api_key_auth():
    session = RecordingSession(
        [DummyResponse(201, {'sandboxID': 'sbx123', 'templateID': 'base'})])
    client = SandboxClient(api_key='api-key', session=session)

    client.create_sandbox(resources=[KodoResource(
        bucket='bucket',
        mount_path='/mnt/bucket',
        access_key='resource-ak',
        secret_key='resource-sk',
    )])

    req = session.requests[0]
    assert req.headers['Authorization'] == 'Bearer api-key'
    assert body_of(req)['resources'][0]['access_key'] == 'resource-ak'
    assert body_of(req)['resources'][0]['secret_key'] == 'resource-sk'


def test_create_rejects_partial_inline_kodo_credentials():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(ValueError, match='access_key and secret_key'):
        client.create_sandbox(resources=[{
            'type': 'kodo',
            'bucket': 'bucket',
            'mount_path': '/mnt/bucket',
            'access_key': 'resource-ak',
        }])


def test_create_with_saved_injection_rule_requires_qiniu_credentials(
        monkeypatch):
    monkeypatch.delenv('QINIU_SANDBOX_ACCESS_KEY', raising=False)
    monkeypatch.delenv('QINIU_SANDBOX_SECRET_KEY', raising=False)
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


def test_create_with_saved_injection_rule_accepts_snake_case_rule_id():
    session = RecordingSession(
        [DummyResponse(201, {'sandboxID': 'sbx123', 'templateID': 'base'})])
    client = SandboxClient(access_key='ak', secret_key='sk', session=session)

    client.create_sandbox(injections=[{
        'type': 'id',
        'rule_id': 'rule-1',
    }])

    assert body_of(session.requests[0])['injections'] == [{
        'type': 'id',
        'ruleID': 'rule-1',
    }]


def test_create_sandbox_normalizes_inline_injection_match_conditions():
    session = RecordingSession(
        [DummyResponse(201, {'sandboxID': 'sbx123', 'templateID': 'base'})])
    client = SandboxClient(api_key='api-key', session=session)

    client.create_sandbox(injections=[{
        'type': 'openai',
        'apiKey': 'openai-key',
        'baseUrl': 'https://api.openai.com/v1/*',
        'ifHeaders': {'X-Tenant': 'tenant-1'},
        'ifQueries': {'model': 'gpt-4o-mini'},
    }])

    assert body_of(session.requests[0])['injections'] == [{
        'type': 'openai',
        'api_key': 'openai-key',
        'base_url': 'https://api.openai.com/v1/*',
        'if_headers': {'X-Tenant': 'tenant-1'},
        'if_queries': {'model': 'gpt-4o-mini'},
    }]


def test_injection_rule_requests_normalize_match_conditions():
    session = RecordingSession([DummyResponse(201, {'ruleID': 'rule-1'})])
    client = SandboxClient(access_key='ak', secret_key='sk', session=session)

    client.create_injection_rule(
        name='conditional-openai',
        injection={
            'type': 'openai',
            'apiKey': 'openai-key',
            'baseUrl': 'https://api.openai.com/v1/*',
            'ifHeaders': {'X-Tenant': 'tenant-1'},
            'ifQueries': {'model': 'gpt-4o-mini'},
        },
    )

    assert body_of(session.requests[0]) == {
        'name': 'conditional-openai',
        'injection': {
            'type': 'openai',
            'api_key': 'openai-key',
            'base_url': 'https://api.openai.com/v1/*',
            'if_headers': {'X-Tenant': 'tenant-1'},
            'if_queries': {'model': 'gpt-4o-mini'},
        },
    }


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


def test_client_truncates_long_text_error_responses():
    class TextErrorResponse(ErrorResponse):
        def json(self):
            raise ValueError('not json')

    client = SandboxClient(
        api_key='api-key',
        session=RecordingSession([TextErrorResponse(502)]))
    client.session.responses[0].text = '<html>' + ('x' * 300) + '</html>'

    with pytest.raises(SandboxError) as err:
        client.list_sandboxes()

    assert len(str(err.value)) < 260
    assert str(err.value).endswith('...')


def test_client_falls_back_to_content_when_error_text_fails():
    class BrokenTextResponse(object):
        status_code = 502
        content = b'raw error bytes'
        headers = {}

        def json(self):
            raise ValueError('not json')

        @property
        def text(self):
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad')

    client = SandboxClient(
        api_key='api-key',
        session=RecordingSession([BrokenTextResponse()]))

    with pytest.raises(SandboxError) as err:
        client.list_sandboxes()

    assert err.value.data == b'raw error bytes'


def test_client_includes_nested_error_message_in_api_errors():
    client = SandboxClient(
        api_key='api-key',
        session=RecordingSession([DummyResponse(400, {
            'error': {'message': 'bad sandbox request'},
        })]))

    with pytest.raises(SandboxError) as err:
        client.list_sandboxes()

    assert 'bad sandbox request' in str(err.value)


def test_access_token_auth_requires_access_token():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.rebuild_template('tmpl123')

    assert 'access_token is required' in str(err.value)


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
    assert session.requests[2].url.endswith('/v2/sandboxes/sbx123/connect')
    assert body_of(session.requests[2]) == {'timeout': 45}


def test_connect_sandbox_uses_timeout_body_only():
    session = RecordingSession([DummyResponse(200, {'sandboxID': 'sbx123'})])
    client = SandboxClient(api_key='api-key', session=session)

    client.connect_sandbox('sbx123', timeout=9)

    assert body_of(session.requests[0]) == {'timeout': 9}


def test_sandbox_control_methods_require_sandbox_id():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError):
        client.pause_sandbox('')
    with pytest.raises(SandboxError):
        client.resume_sandbox(None)
    with pytest.raises(SandboxError):
        client.connect_sandbox('')
    with pytest.raises(SandboxError):
        client.update_sandbox_timeout(None, 30)
    with pytest.raises(SandboxError):
        client.refresh_sandbox('')
    with pytest.raises(SandboxError):
        client.update_sandbox(None)
    with pytest.raises(SandboxError):
        client.get_sandbox_metrics('')
    with pytest.raises(SandboxError):
        client.get_sandbox_logs(None)

    assert client.session.requests == []


def test_sandbox_connect_forwards_envd_options_to_instance():
    session = RecordingSession([DummyResponse(200, {'sandboxID': 'sbx123'})])
    client = SandboxClient(api_key='api-key', session=session)

    sandbox = Sandbox.connect(
        'sbx123',
        client=client,
        envd_url='http://envd.local',
        envdAccessToken='envd-token',
    )

    assert sandbox.envd_url() == 'http://envd.local'
    assert sandbox.envdAccessToken == 'envd-token'
    assert body_of(session.requests[0]) == {}


def test_delete_template_requires_template_id():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.delete_template(None)

    assert 'template_id is required' in str(err.value)


def test_list_default_templates_uses_public_endpoint():
    templates = [
        {
            'templateID': 'tmpl-default-1',
            'names': ['qiniu/code-interpreter'],
            'buildStatus': 'ready',
        },
        {
            'templateID': 'tmpl-default-2',
            'names': ['qiniu/python'],
            'buildStatus': 'ready',
        },
    ]
    session = RecordingSession([DummyResponse(200, templates)])
    client = SandboxClient(api_key='api-key', session=session)

    result = client.list_default_templates()

    assert result == templates
    request = session.requests[0]
    assert request.method == 'GET'
    assert request.url == DEFAULT_ENDPOINT + '/default-templates'


def test_list_default_templates_raises_sandbox_error_on_api_error():
    session = RecordingSession([
        DummyResponse(401, {'message': 'unauthorized'}),
    ])
    client = SandboxClient(api_key='api-key', session=session)

    with pytest.raises(SandboxError) as err:
        client.list_default_templates()

    assert 'status 401: unauthorized' in str(err.value)
    assert err.value.response.status_code == 401
    assert err.value.data == {'message': 'unauthorized'}


def test_list_default_templates_camel_case_alias():
    templates = [{'templateID': 'tmpl-default'}]
    session = RecordingSession([DummyResponse(200, templates)])
    client = SandboxClient(api_key='api-key', session=session)

    assert client.listDefaultTemplates() == templates
    assert session.requests[0].url == DEFAULT_ENDPOINT + '/default-templates'


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


def test_envd_url_requires_domain_without_override():
    sandbox = Sandbox(info={'sandboxID': 'sbx123'})

    with pytest.raises(SandboxError):
        sandbox.envd_url()


def test_file_url_accepts_none_signature_expiration():
    sandbox = Sandbox(info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
        'envdAccessToken': 'token',
    })

    url = sandbox.download_url('/tmp/hello.txt', signatureExpiration=None)
    query = parse_qs(urlparse(url).query)

    assert query['signature'][0]
    assert query['signature'][0] == file_signature(
        '/tmp/hello.txt',
        'read',
        'user',
        'token',
        '',
    )
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


def test_wait_for_ready_caps_sleep_to_remaining_timeout(monkeypatch):
    session = RecordingSession([
        DummyResponse(503, {}),
        DummyResponse(503, {}),
    ])
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
    })
    times = iter([0, 2.5, 3])
    sleeps = []
    monkeypatch.setattr(
        sandbox_module, '_monotonic_time', lambda: next(times))
    monkeypatch.setattr(sandbox_module.time, 'sleep', sleeps.append)

    with pytest.raises(SandboxError):
        sandbox.wait_for_ready(timeout=3, interval=2)

    assert sleeps == [0.5]


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
    assert len(session.requests) == 1


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
    assert 'next_token' not in client.calls[0]
    assert client.calls[1]['nextToken'] == 'next-page'


def test_sandbox_paginator_does_not_send_client_credentials_as_filters():
    client = RecordingSandboxListClient()
    paginator = SandboxPaginator(
        client=client,
        api_key='api-key',
        access_token='access-token',
        endpoint='https://sandbox.example.test',
        metadata={'app': 'tests'},
    )

    paginator.next_items()

    assert client.calls[0] == {'metadata': {'app': 'tests'}}


def test_list_sandboxes_v2_serializes_metadata_dict_as_query_string():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(query={
        'metadata': {'app': 'tests'},
        'state': 'running',
    })

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['metadata'] == ['app=tests']
    assert query['state'] == ['running']


def test_list_sandboxes_v2_accepts_metadata_string():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(metadata='user=abc&app=prod')

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['metadata'] == ['user=abc&app=prod']


def test_list_sandboxes_v2_serializes_template_filters_as_comma_string():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(template=['python', 'team/node'])

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['template'] == ['python,team/node']


def test_list_sandboxes_v2_serializes_array_filters_from_query_options():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(query={
        'template': ['python', 'team/node'],
        'state': ['running', 'paused'],
        'limit': 10,
        'nextToken': 'next-page',
    })

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['template'] == ['python,team/node']
    assert query['state'] == ['running,paused']
    assert query['limit'] == ['10']
    assert query['nextToken'] == ['next-page']


def test_list_sandboxes_v2_explicit_options_override_extra_query_values():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(
        limit=20,
        state=['running'],
        template=['python'],
        query={
            'limit': 10,
            'state': ['paused'],
            'template': ['node'],
        },
    )

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['limit'] == ['20']
    assert query['state'] == ['running']
    assert query['template'] == ['python']


def test_list_sandboxes_v2_explicit_none_options_override_query_values():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(
        metadata=None,
        state=None,
        template=None,
        query={
            'metadata': {'app': 'tests'},
            'state': ['paused'],
            'template': ['node'],
        },
    )

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert 'metadata' not in query
    assert 'state' not in query
    assert 'template' not in query


def test_list_sandboxes_v2_serializes_non_string_filter_values():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(template=[123, 456], state=7)

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['template'] == ['123,456']
    assert query['state'] == ['7']


def test_list_sandboxes_v2_does_not_join_mapping_keys():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(template={'template': 'python'})

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['template'] == ["{'template': 'python'}"]


def test_list_sandboxes_v2_preserves_bytes_and_unicode_filter_values():
    session = RecordingSession([DummyResponse(200, {'items': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.list_sandboxes_v2(
        template=[u'团队/模板', b'team/node'],
        state=[b'running'],
    )

    query = parse_qs(urlparse(session.requests[0].url).query)
    template_value = query['template'][0]
    if not isinstance(template_value, type(u'')):
        template_value = template_value.decode('utf-8')
    assert template_value == u'团队/模板,team/node'
    assert query['state'] == ['running']


def test_template_responses_preserve_names_and_ownership_metadata():
    session = RecordingSession([DummyResponse(200, {
        'templateID': 'tmpl123',
        'aliases': ['python'],
        'names': ['qiniu/python'],
        'isOwner': False,
        'builds': [],
    })])
    client = SandboxClient(api_key='api-key', session=session)

    template = client.get_template('tmpl123')

    assert template['aliases'] == ['python']
    assert template['names'] == ['qiniu/python']
    assert template['isOwner'] is False
    assert template['builds'] == []


def test_get_sandbox_injections_returns_current_rules():
    session = RecordingSession([DummyResponse(200, {
        'injections': [{'type': 'id', 'ruleID': 'rule123'}],
    })])
    client = SandboxClient(api_key='api-key', session=session)

    result = client.get_sandbox_injections('sandbox/id')

    assert result == {
        'injections': [{'type': 'id', 'ruleID': 'rule123'}],
    }
    request = session.requests[0]
    assert request.method == 'GET'
    assert request.url == (
        DEFAULT_ENDPOINT + '/sandboxes/sandbox%2Fid/injections')


def test_update_sandbox_injections_replaces_normalized_rules():
    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    result = client.update_sandbox_injections('sbx123', [{
        'type': 'openai',
        'baseUrl': 'https://api.openai.com/v1/*',
        'apiKey': 'secret',
    }])

    assert result is None
    request = session.requests[0]
    assert request.method == 'PUT'
    assert request.url == DEFAULT_ENDPOINT + '/sandboxes/sbx123/injections'
    assert body_of(request) == {'injections': [{
        'type': 'openai',
        'base_url': 'https://api.openai.com/v1/*',
        'api_key': 'secret',
    }]}


def test_update_sandbox_injections_accepts_empty_replacement():
    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    assert client.update_sandbox_injections('sbx123', []) is None
    assert body_of(session.requests[0]) == {'injections': []}


def test_update_sandbox_injections_wraps_single_rule():
    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    client.update_sandbox_injections('sbx123', {
        'type': 'http',
        'baseUrl': 'https://api.example.com/*',
    })

    assert body_of(session.requests[0]) == {'injections': [{
        'type': 'http',
        'base_url': 'https://api.example.com/*',
    }]}


def test_update_sandbox_injections_wraps_single_rule_object():
    class InjectionRule(object):
        def to_dict(self):
            return {
                'type': 'openai',
                'apiKey': 'secret',
            }

    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    client.update_sandbox_injections('sbx123', InjectionRule())

    assert body_of(session.requests[0]) == {'injections': [{
        'type': 'openai',
        'api_key': 'secret',
    }]}


def test_update_sandbox_injections_requires_rules_value():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.update_sandbox_injections('sbx123', None)

    assert 'injections is required' in str(err.value)
    assert client.session.requests == []


@pytest.mark.parametrize('injections', [
    'invalid-string-injection',
    b'invalid-bytes-injection',
])
def test_update_sandbox_injections_rejects_string_value(injections):
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.update_sandbox_injections('sbx123', injections)

    assert 'injections must be a list, dict, or rule object' in str(err.value)
    assert client.session.requests == []


def test_update_sandbox_injections_rejects_non_iterable_scalar():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.update_sandbox_injections('sbx123', 123)

    assert 'injections must be a list, dict, or rule object' in str(err.value)
    assert client.session.requests == []


def test_update_sandbox_github_token_uses_api_field_name():
    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    result = client.update_sandbox_github_token(
        'sbx123', authorization_token='github-token')

    assert result is None
    request = session.requests[0]
    assert request.method == 'PUT'
    assert request.url == DEFAULT_ENDPOINT + '/sandboxes/sbx123/github-token'
    assert body_of(request) == {'authorization_token': 'github-token'}


def test_update_sandbox_github_token_accepts_camel_case_alias():
    session = RecordingSession([DummyResponse(204)])
    client = SandboxClient(api_key='api-key', session=session)

    client.update_sandbox_github_token(
        'sbx123', authorizationToken='github-token')

    assert body_of(session.requests[0]) == {
        'authorization_token': 'github-token',
    }


def test_update_sandbox_github_token_requires_token():
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        client.update_sandbox_github_token('sbx123')

    assert 'authorization_token is required' in str(err.value)
    assert client.session.requests == []


@pytest.mark.parametrize('method,args', [
    ('get_sandbox_injections', ()),
    ('update_sandbox_injections', ([],)),
    ('update_sandbox_github_token', ('github-token',)),
])
def test_runtime_configuration_methods_require_sandbox_id(method, args):
    client = SandboxClient(api_key='api-key', session=RecordingSession())

    with pytest.raises(SandboxError) as err:
        getattr(client, method)(None, *args)

    assert 'sandbox_id is required' in str(err.value)
    assert client.session.requests == []


def test_runtime_configuration_camel_case_aliases():
    session = RecordingSession([
        DummyResponse(200, {'injections': []}),
        DummyResponse(204),
        DummyResponse(204),
    ])
    client = SandboxClient(api_key='api-key', session=session)

    assert client.getSandboxInjections('sbx123') == {'injections': []}
    assert client.updateSandboxInjections('sbx123', []) is None
    assert client.updateSandboxGithubToken('sbx123', 'github-token') is None

    assert [request.method for request in session.requests] == [
        'GET', 'PUT', 'PUT',
    ]


def test_sandbox_runtime_configuration_helpers_delegate_to_client():
    class RuntimeConfigClient(object):
        def __init__(self):
            self.calls = []

        def get_sandbox_injections(self, sandbox_id):
            self.calls.append(('get', sandbox_id))
            return {'injections': []}

        def update_sandbox_injections(self, sandbox_id, injections):
            self.calls.append(('injections', sandbox_id, injections))

        def update_sandbox_github_token(self, sandbox_id, token):
            self.calls.append(('github', sandbox_id, token))

    client = RuntimeConfigClient()
    sandbox = Sandbox(client=client, sandbox_id='sbx123')

    assert sandbox.get_injections() == {'injections': []}
    assert sandbox.update_injections([{'type': 'id', 'ruleID': 'rule123'}]) \
        is None
    assert sandbox.update_github_token('github-token') is None
    assert client.calls == [
        ('get', 'sbx123'),
        ('injections', 'sbx123', [{'type': 'id', 'ruleID': 'rule123'}]),
        ('github', 'sbx123', 'github-token'),
    ]


def test_sandbox_runtime_configuration_camel_case_aliases_delegate():
    class RuntimeConfigClient(object):
        def get_sandbox_injections(self, sandbox_id):
            return {'sandboxID': sandbox_id, 'injections': []}

        def update_sandbox_injections(self, sandbox_id, injections):
            return sandbox_id, injections

        def update_sandbox_github_token(self, sandbox_id, token):
            return sandbox_id, token

    sandbox = Sandbox(client=RuntimeConfigClient(), sandbox_id='sbx123')

    assert sandbox.getInjections()['sandboxID'] == 'sbx123'
    assert sandbox.updateInjections([]) == ('sbx123', [])
    assert sandbox.updateGithubToken('token') == ('sbx123', 'token')


def test_sandbox_github_token_helper_forwards_keyword_aliases():
    class RuntimeConfigClient(object):
        def update_sandbox_github_token(
                self, sandbox_id, authorization_token=None, **opts):
            return sandbox_id, authorization_token, opts

    sandbox = Sandbox(client=RuntimeConfigClient(), sandbox_id='sbx123')

    assert sandbox.update_github_token(token='token') == (
        'sbx123', None, {'token': 'token'},
    )
    assert sandbox.updateGithubToken(authorizationToken='camel-token') == (
        'sbx123', None, {'authorizationToken': 'camel-token'},
    )


def test_wait_for_build_retries_transient_sandbox_errors(monkeypatch):
    class BuildClient(SandboxClient):
        def __init__(self):
            super(BuildClient, self).__init__(
                api_key='api-key',
                session=RecordingSession(),
            )
            self.calls = 0

        def get_template_build_status(self, template_id, build_id, **opts):
            del template_id, build_id, opts
            self.calls += 1
            if self.calls == 1:
                raise SandboxError('temporary gateway error')
            return {'status': 'ready', 'templateID': 'tmpl123'}

    monkeypatch.setattr(
        'qiniu.services.sandbox.client.time.sleep',
        lambda x: x,
    )
    client = BuildClient()

    assert client.wait_for_build('tmpl123', 'build123', interval=0) == {
        'status': 'ready',
        'templateID': 'tmpl123',
    }
    assert client.calls == 2


def test_wait_for_build_reraises_permanent_sandbox_errors(monkeypatch):
    class BuildClient(SandboxClient):
        def __init__(self):
            super(BuildClient, self).__init__(
                api_key='api-key',
                session=RecordingSession(),
            )
            self.calls = 0

        def get_template_build_status(self, template_id, build_id, **opts):
            del template_id, build_id, opts
            self.calls += 1
            raise SandboxError('missing build', DummyResponse(404, {}))

    monkeypatch.setattr(
        'qiniu.services.sandbox.client.time.sleep',
        lambda x: x,
    )
    client = BuildClient()

    with pytest.raises(SandboxError) as err:
        client.wait_for_build('tmpl123', 'build123', interval=0)

    assert err.value.status_code == 404
    assert client.calls == 1


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


def test_is_running_returns_false_without_domain():
    session = RecordingSession()
    sandbox = Sandbox(client=SandboxClient(
        api_key='api-key',
        session=session,
    ), info={'sandboxID': 'sbx123'})

    assert sandbox.is_running() is False
    assert session.requests == []


def test_get_sandboxes_metrics_serializes_ids_as_comma_string():
    session = RecordingSession([DummyResponse(200, {'metrics': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.get_sandboxes_metrics(['sbx1', 'sbx2'])

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['sandbox_ids'] == ['sbx1,sbx2']


def test_get_sandboxes_metrics_accepts_set_values():
    session = RecordingSession([DummyResponse(200, {'metrics': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.get_sandboxes_metrics(set(['sbx1', 'sbx2']))

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert set(query['sandbox_ids'][0].split(',')) == set(['sbx1', 'sbx2'])


def test_get_sandboxes_metrics_accepts_generator_values():
    session = RecordingSession([DummyResponse(200, {'metrics': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.get_sandboxes_metrics(item for item in ['sbx1', 'sbx2'])

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['sandbox_ids'] == ['sbx1,sbx2']


def test_get_sandboxes_metrics_accepts_single_sandbox_dict():
    session = RecordingSession([DummyResponse(200, {'metrics': []})])
    client = SandboxClient(api_key='api-key', session=session)

    client.get_sandboxes_metrics({'id': 'sbx123'})

    query = parse_qs(urlparse(session.requests[0].url).query)
    assert query['sandbox_ids'] == ['sbx123']


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
        .run_cmd(['python', '-m', 'pip', 'install', 'pytest'])
        .copy('/local/app.py', '/app/app.py')
        .set_env('PYTHONUNBUFFERED', '1')
        .set_start_cmd('python /app/app.py')
    )

    assert template.to_dict() == {
        'fromImage': 'python:3.11',
        'steps': [
            {'type': 'RUN', 'args': ['pip install qiniu']},
            {'type': 'RUN', 'args': ['python -m pip install pytest']},
            {'type': 'COPY', 'args': ['/local/app.py', '/app/app.py']},
            {'type': 'ENV', 'args': ['PYTHONUNBUFFERED', '1']},
        ],
        'startCmd': 'python /app/app.py',
    }


def test_template_ready_cmd_helpers_align_with_e2b():
    ready = wait_for_port(8000)
    assert isinstance(ready, ReadyCmd)
    assert ready.get_cmd() == (
        "ss -tuln | awk '{print $5}' | grep -E '(^|:)8000$'")
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
    assert template.to_dict()['readyCmd'] == (
        "ss -tuln | awk '{print $5}' | grep -E '(^|:)8000$'")


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
                'exit_code': -1,
                'wait': lambda self: result,
            })()
        return result

    def send_stdin(self, pid, data):
        self.calls.append(('send_stdin', {'pid': pid, 'data': data}))
        return None

    def close_stdin(self, pid):
        self.calls.append(('close_stdin', {'pid': pid}))
        return None


class RecordingFiles(object):
    def __init__(self):
        self.writes = []
        self.removes = []

    def write(self, path, data, **opts):
        self.writes.append((path, data, opts))
        return None

    def remove(self, path, **opts):
        self.removes.append((path, opts))
        return None


def attach_recording_files(commands):
    files = RecordingFiles()
    commands.sandbox = type('Sandbox', (object,), {'files': files})()
    return files


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
    git.set_config('user.name', 'tester', scope='local', path='/repo')
    git.get_config('user.name', scope='local', path='/repo')

    assert commands.calls[0][0] == (
        'git remote add origin https://github.com/qiniu/repo.git')
    assert commands.calls[1][0] == 'git remote get-url origin'
    assert commands.calls[2][0] == (
        "git branch '--format=%(refname:short)\t%(HEAD)'")
    assert commands.calls[3][0] == 'git checkout -b feature'
    assert commands.calls[4][0] == 'git checkout main'
    assert commands.calls[5][0] == 'git branch -D old'
    assert commands.calls[6][0] == "git reset --hard 'HEAD~1'"
    assert commands.calls[7][0] == 'git restore -- a.txt b.txt'
    assert commands.calls[8][0] == 'git config --local user.name tester'
    assert commands.calls[8][1]['cwd'] == '/repo'
    assert commands.calls[9][0] == 'git config --local --get user.name'
    assert commands.calls[9][1]['cwd'] == '/repo'


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

    assert commands.calls[0][0] == 'git add -- README.md'
    assert commands.calls[1][0] == 'git restore -- README.md'
    assert commands.calls[2][0] == 'git restore -- setup.py'


def test_git_add_and_restore_use_path_separator_for_dash_paths():
    commands = RecordingCommands()
    git = Git(commands)

    git.add('/repo', files='--intent-to-add')
    git.restore('/repo', paths='--worktree')

    assert commands.calls[0][0] == "git add -- --intent-to-add"
    assert commands.calls[1][0] == "git restore -- --worktree"


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


def test_git_dangerously_authenticate_uses_stdin_with_real_sandbox():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
    git = Git(commands)

    git.dangerously_authenticate(
        username='git-user',
        password='secret-%-token',
        host='github.com',
        protocol='https',
    )

    assert files.writes == []
    assert files.removes == []
    assert commands.calls[1][0] == 'git credential approve'
    assert commands.calls[2][1]['data'] == (
        'protocol=https\nhost=github.com\n'
        'username=git-user\npassword=secret-%-token\n\n'
    )


def test_git_dangerously_authenticate_ignores_background_for_stdin_flow():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
    git = Git(commands)

    git.dangerously_authenticate(
        username='git-user',
        password='secret-token',
        background=True,
    )

    assert 'background' not in commands.calls[0][1]
    assert commands.calls[1][1]['background'] is True
    assert 'background' not in commands.calls[2][1]
    assert 'background' not in commands.calls[3][1]
    assert files.writes == []
    assert files.removes == []


def test_git_status_and_branches_return_structured_e2b_types():
    commands = RecordingCommands()
    commands.results = [
        type('Result', (object,), {
            'exit_code': 0,
            'stdout': (
                '## main...origin/main [ahead 2, behind 1]\n'
                ' M changed.txt\n'
                'A  staged.txt\n'
                ' M my -> file.txt\n'
                'R  old.txt -> renamed.txt\n'
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
    assert status.file_status[2].name == 'my -> file.txt'
    assert status.file_status[2].renamed_from is None
    assert status.file_status[3].name == 'renamed.txt'
    assert status.file_status[3].renamed_from == 'old.txt'
    assert isinstance(branches, GitBranches)
    assert branches.branches == ['main', 'feature']
    assert branches.current_branch == 'main'


def test_git_status_raises_when_git_command_fails():
    commands = RecordingCommands()
    commands.results = [type('Result', (object,), {
        'exit_code': 128,
        'stdout': '',
        'stderr': 'fatal: not a git repository',
        'error': '',
    })()]
    git = Git(commands)

    with pytest.raises(CommandExitError):
        git.status('/not-a-repo')


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


def test_git_credentials_require_username_with_password():
    git = Git(RecordingCommands())

    with pytest.raises(InvalidArgumentException):
        git.pull('/repo', password='secret')
    with pytest.raises(InvalidArgumentException):
        git.push('/repo', password='secret')


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


def test_git_push_with_credentials_uses_askpass_without_remote_url_leak():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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
    assert commands.calls[1][0] == 'install -d -m 700 /tmp/qiniu-git-auth'
    assert files.writes[0][0].startswith(
        '/tmp/qiniu-git-auth/qiniu-git-askpass-')
    assert commands.calls[2][0].startswith(
        'chmod 700 /tmp/qiniu-git-auth/qiniu-git-askpass-')
    assert commands.calls[3][0] == 'git push --set-upstream origin main'
    assert 'secret:%@token' not in commands.calls[3][0]
    assert commands.calls[3][1]['request_timeout'] == 7
    assert commands.calls[3][1]['envs']['GIT_ASKPASS'] == files.writes[0][0]
    assert commands.calls[3][1]['envs']['GIT_USERNAME'] == 'git:user'
    assert commands.calls[3][1]['envs']['GIT_PASSWORD'] == 'secret:%@token'
    assert files.removes == [(files.writes[0][0], {})]


def test_git_pull_with_credentials_resolves_single_remote():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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
    assert commands.calls[2][0] == 'install -d -m 700 /tmp/qiniu-git-auth'
    assert commands.calls[4][0] == 'git pull origin main'
    assert 'secret-token' not in commands.calls[4][0]
    assert commands.calls[4][1]['envs']['GIT_ASKPASS'] == files.writes[0][0]
    assert files.removes == [(files.writes[0][0], {})]


def test_git_credential_helpers_ignore_background_when_reading_remote():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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

    handle = git.pull(
        '/repo',
        branch='main',
        username='git-user',
        password='secret-token',
        background=True,
    )

    assert 'background' not in commands.calls[0][1]
    assert 'background' not in commands.calls[1][1]
    assert commands.calls[4][1]['background'] is True
    assert files.removes == []
    handle.wait()
    assert files.removes == [(files.writes[0][0], {})]


def test_git_background_throw_on_error_waits_before_raising():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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
            'exit_code': 1,
            'stdout': '',
            'stderr': 'fatal: failed',
            'error': '',
        })(),
    ]
    git = Git(commands)

    handle = git.pull(
        '/repo',
        branch='main',
        username='git-user',
        password='secret-token',
        background=True,
        throw_on_error=True,
    )

    assert files.removes == []
    with pytest.raises(CommandExitError):
        handle.wait()
    assert files.removes == [(files.writes[0][0], {})]


def test_git_background_credentials_clean_up_when_handle_is_discarded():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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

    handle = git.pull(
        '/repo',
        branch='main',
        username='git-user',
        password='secret-token',
        background=True,
    )
    credential_path = files.writes[0][0]
    wait_closure = (
        getattr(handle.wait, '__closure__', None) or
        getattr(handle.wait, 'func_closure', None) or
        []
    )
    for cell in wait_closure:
        try:
            assert cell.cell_contents is not handle
        except ValueError:
            pass

    assert files.removes == []
    del handle
    gc.collect()

    assert files.removes == [(credential_path, {})]


def test_git_push_with_credentials_cleans_askpass_on_auth_failure():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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

    assert commands.calls[-1][0] == 'git push --set-upstream origin'
    assert files.removes == [(files.writes[0][0], {})]


def test_git_push_cleans_askpass_after_operation_exception():
    commands = RecordingCommands()
    files = attach_recording_files(commands)
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
    ]
    git = Git(commands)

    with pytest.raises(SandboxError) as err:
        git._with_remote_credentials(
            '/repo',
            'origin',
            'git-user',
            'bad-token',
            lambda auth_opts: (_ for _ in ()).throw(
                SandboxError('rpc timed out')),
        )

    assert 'rpc timed out' in str(err.value)
    assert files.removes == [(files.writes[0][0], {})]


def test_git_credentials_clean_askpass_when_chmod_raises():
    class ChmodFailCommands(RecordingCommands):
        def run(self, cmd, **opts):
            if cmd.startswith('chmod 700 '):
                raise SandboxError('chmod rpc failed')
            return super(ChmodFailCommands, self).run(cmd, **opts)

    commands = ChmodFailCommands()
    files = attach_recording_files(commands)
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
    ]
    git = Git(commands)

    with pytest.raises(SandboxError):
        git.push(
            '/repo',
            remote='origin',
            username='git-user',
            password='secret-token',
        )

    assert files.removes == [(files.writes[0][0], {})]


def test_git_credentials_clean_askpass_when_write_raises():
    class FailingWriteFiles(RecordingFiles):
        def write(self, path, data, **opts):
            super(FailingWriteFiles, self).write(path, data, **opts)
            raise SandboxError('write rpc failed')

    commands = RecordingCommands()
    files = FailingWriteFiles()
    commands.sandbox = type('Sandbox', (object,), {'files': files})()
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
    ]
    git = Git(commands)

    with pytest.raises(SandboxError):
        git.push(
            '/repo',
            remote='origin',
            username='git-user',
            password='secret-token',
        )

    assert files.removes == [(files.writes[0][0], {})]


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


def test_git_config_helpers_accept_legacy_repo_path_signatures():
    commands = RecordingCommands()
    git = Git(commands)

    git.set_config(None, 'http.version', 'HTTP/1.1', global_config=True)
    git.set_config('/repo', 'user.name', 'Sandbox Demo')
    git.set_config('/repo', 'gitreview.username', 'global')
    git.set_config('repo', 'user.email', 'global')
    git.set_config('.', 'core.editor', 'global')
    git.set_config('my.repo', 'user.signingkey', 'global')
    git.get_config('/repo', 'user.name')

    assert commands.calls[0][0] == "git config --global http.version HTTP/1.1"
    assert 'cwd' not in commands.calls[0][1]
    assert commands.calls[1][0] == (
        "git config --local user.name 'Sandbox Demo'")
    assert commands.calls[1][1]['cwd'] == '/repo'
    assert commands.calls[2][0] == (
        'git config --local gitreview.username global')
    assert commands.calls[2][1]['cwd'] == '/repo'
    assert commands.calls[3][0] == 'git config --local user.email global'
    assert commands.calls[3][1]['cwd'] == 'repo'
    assert commands.calls[4][0] == 'git config --local core.editor global'
    assert commands.calls[4][1]['cwd'] == '.'
    assert commands.calls[5][0] == 'git config --local user.signingkey global'
    assert commands.calls[5][1]['cwd'] == 'my.repo'
    assert commands.calls[6][0] == 'git config --local --get user.name'
    assert commands.calls[6][1]['cwd'] == '/repo'


@pytest.mark.parametrize('opts,expected', [
    ({}, {}),
    ({'min_disk_mb': 0}, {'minDiskMb': 0}),
    ({'min_free_disk_mb': 0}, {'minFreeDiskMb': 0}),
    ({'minDiskMb': 10240, 'minFreeDiskMb': 2048},
     {'minDiskMb': 10240, 'minFreeDiskMb': 2048}),
    ({'min_disk_mb': None, 'min_free_disk_mb': None}, {}),
    ({'disk_size_mb': None, 'diskSizeMB': None}, {}),
])
def test_template_disk_constraints_preserve_zero_and_omission(opts, expected):
    session = RecordingSession()
    SandboxClient(api_key='key', session=session).create_template(**opts)
    assert body_of(session.requests[0]) == expected


@pytest.mark.parametrize('opts', [
    {'disk_size_mb': 10240}, {'diskSizeMB': 10240},
    {'min_disk_mb': 0, 'minDiskMb': 10240},
    {'min_free_disk_mb': 0, 'minFreeDiskMb': 10240},
])
def test_template_disk_constraints_reject_legacy_or_conflicting_options(opts):
    client = SandboxClient(api_key='key', session=RecordingSession())
    with pytest.raises(SandboxError):
        client.create_template(**opts)
    assert client.session.requests == []


@pytest.mark.parametrize('opts,expected', [
    ({}, {}),
    ({'auto_pause_memory': False, 'auto_resume': False},
     {'autoPauseMemory': False, 'autoResume': {'enabled': False}}),
    ({'autoPause': True, 'autoPauseMemory': True,
      'autoResume': {'enabled': True}},
     {'autoPause': True, 'autoPauseMemory': True,
      'autoResume': {'enabled': True}}),
    ({'lifecycle': {'on_timeout': 'pause', 'keep_memory': False,
                    'auto_resume': False}},
     {'autoPause': True, 'autoPauseMemory': False,
      'autoResume': {'enabled': False}}),
    ({'lifecycle': {'onTimeout': 'pause', 'keepMemory': True,
                    'autoResume': True}},
     {'autoPause': True, 'autoPauseMemory': True,
      'autoResume': {'enabled': True}}),
])
def test_create_auto_pause_and_resume_fields(opts, expected):
    session = RecordingSession()
    SandboxClient(api_key='key', session=session).create_sandbox(**opts)
    body = body_of(session.requests[0])
    assert {key: value for key, value in body.items()
            if key.startswith('auto')} == expected


@pytest.mark.parametrize('opts', [
    {'auto_pause_memory': False, 'auto_resume': True},
    {'autoPauseMemory': False, 'autoResume': {'enabled': True}},
    {'auto_resume': True, 'autoResume': False},
    {'lifecycle': {'on_timeout': 'pause', 'keep_memory': False,
                   'auto_resume': True}},
    {'auto_pause_memory': True, 'lifecycle': {'keep_memory': False}},
])
def test_create_rejects_conflicting_auto_resume_options(opts):
    client = SandboxClient(api_key='key', session=RecordingSession())
    with pytest.raises(SandboxError):
        client.create_sandbox(**opts)
    assert client.session.requests == []


@pytest.mark.parametrize('memory,expected', [
    (None, {}), (False, {'memory': False}), (True, {'memory': True}),
])
def test_pause_supports_memory_choice(memory, expected):
    session = RecordingSession([DummyResponse(204)])
    sandbox = Sandbox(sandbox_id='sb/id', client=SandboxClient(
        api_key='key', session=session))
    assert sandbox.pause(memory=memory) is None
    assert session.requests[0].method == 'POST'
    assert session.requests[0].url == DEFAULT_ENDPOINT + '/sandboxes/sb%2Fid/pause'
    assert body_of(session.requests[0]) == expected


@pytest.mark.parametrize('status', [200, 201])
@pytest.mark.parametrize('timeout,expected', [(None, {}), (60, {'timeout': 60})])
def test_connect_uses_v2_and_server_default(status, timeout, expected):
    session = RecordingSession([DummyResponse(status, {
        'sandboxID': 'sb/id', 'envdAccessToken': 'new-token',
    })])
    client = SandboxClient(api_key='key', session=session)
    sandbox = Sandbox.connect('sb/id', client=client, timeout=timeout)
    assert sandbox.envd_access_token == 'new-token'
    assert session.requests[0].method == 'POST'
    assert session.requests[0].url == DEFAULT_ENDPOINT + '/v2/sandboxes/sb%2Fid/connect'
    assert body_of(session.requests[0]) == expected


@pytest.mark.parametrize('failure', [
    DummyResponse(408), DummyResponse(502), DummyResponse(504),
    DummyResponse(503, {'error_code': 'api_shutdown'}),
    requests.Timeout('unknown capture outcome'),
    requests.ConnectionError('connection lost'),
    requests.exceptions.ChunkedEncodingError('response interrupted'),
])
def test_snapshot_retry_reuses_key_and_body(monkeypatch, failure):
    sleeps = []
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', sleeps.append)
    session = RecordingSession([failure, DummyResponse(201, {
        'snapshotID': 'snapshot-1', 'names': ['team/demo:v1'],
    })])
    sandbox = Sandbox(client=SandboxClient(api_key='key', session=session),
                      sandbox_id='source/id')
    result = sandbox.create_snapshot('capture-1', memory=False, name='demo:v1')
    assert result['snapshotID'] == 'snapshot-1'
    assert len(session.requests) == 2
    assert len(sleeps) == 1
    for req in session.requests:
        assert req.method == 'POST'
        assert req.url == DEFAULT_ENDPOINT + '/sandboxes/source%2Fid/snapshots'
        assert req.headers['Idempotency-Key'] == b'capture-1'
        assert body_of(req) == {'memory': False, 'name': 'demo:v1'}


@pytest.mark.parametrize('status,code', [
    (400, None), (404, None), (409, None), (500, None),
    (503, None), (503, 'capture_failed'),
])
def test_snapshot_does_not_retry_terminal_errors(monkeypatch, status, code):
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    session = RecordingSession([DummyResponse(status, {'error_code': code})])
    client = SandboxClient(api_key='key', session=session)
    with pytest.raises(SandboxError) as err:
        client.create_sandbox_snapshot('sb', 'key')
    assert err.value.error_code == code
    assert len(session.requests) == 1


@pytest.mark.parametrize('value,expected', [
    ('7', 7), ('0', 0), (' 7 ', 7), (b'7', 7),
    ('bad', None), ('-1', None), ('', None), (None, None),
    (u'\u00b2', None), (u'\u0667', None), (b'\xff', None),
    ('9' * 5000, None), ('2147483648', None),
])
def test_snapshot_honors_valid_retry_after(monkeypatch, value, expected):
    sleeps = []
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', sleeps.append)
    failed = DummyResponse(408)
    failed.headers['Retry-After'] = value
    client = SandboxClient(api_key='key', session=RecordingSession([
        failed, DummyResponse(201, {'snapshotID': 'snapshot-1', 'names': []})]))
    client.create_sandbox_snapshot('sb', 'key')
    assert len(sleeps) == 1
    if expected is not None:
        assert sleeps == [expected]
    else:
        assert 0.5 <= sleeps[0] <= 0.75


@pytest.mark.parametrize('retry_after', ['2100', '2161', '2147483647'])
def test_snapshot_rejects_retry_after_beyond_retention(monkeypatch, retry_after):
    sleeps = []
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', sleeps.append)
    monkeypatch.setattr(sandbox_client_module, '_monotonic_time', lambda: 0)
    failed = DummyResponse(408, {'message': 'still capturing'})
    failed.headers['Retry-After'] = retry_after
    session = RecordingSession([failed])
    client = SandboxClient(api_key='key', session=session)
    with pytest.raises(SandboxError, match='outcome may be unknown') as err:
        client.create_snapshot('sb', 'persisted-key')
    assert len(session.requests) == 1
    assert sleeps == []
    assert err.value.response is failed
    assert err.value.data == {'message': 'still capturing'}
    assert err.value.cause.status_code == 408


@pytest.mark.parametrize('durations,oversleep,expected_sleeps', [
    ([2100], 0, []),
    ([2099.5], 0, []),
    ([1000, 1099.5], 0, [0.5]),
    ([0], 2100, [0.5]),
])
def test_snapshot_retry_budget_includes_requests_and_sleeps(
        monkeypatch, durations, oversleep, expected_sleeps):
    clock = [0]
    sleeps = []
    monkeypatch.setattr(sandbox_client_module, '_monotonic_time', lambda: clock[0])
    monkeypatch.setattr(sandbox_client_module.random, 'random', lambda: 0)

    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay + oversleep

    monkeypatch.setattr(sandbox_client_module.time, 'sleep', sleep)
    session = RecordingSession([requests.Timeout('unknown outcome')
                                for _ in durations])
    send = session.send

    def timed_send(request, **kwargs):
        clock[0] += durations[len(session.requests)]
        return send(request, **kwargs)

    monkeypatch.setattr(session, 'send', timed_send)
    client = SandboxClient(api_key='key', session=session, max_retries=10000)
    with pytest.raises(SandboxError, match='outcome may be unknown') as err:
        client.create_snapshot('sb', 'persisted-key', memory=False)
    assert isinstance(err.value.cause.cause, requests.Timeout)
    assert len(session.requests) == len(durations)
    assert sleeps == expected_sleeps
    assert all(req.headers['Idempotency-Key'] == b'persisted-key'
               for req in session.requests)
    assert all(body_of(req) == {'memory': False} for req in session.requests)


def test_snapshot_retry_can_succeed_within_budget(monkeypatch):
    clock = [0]
    monkeypatch.setattr(sandbox_client_module, '_monotonic_time', lambda: clock[0])

    def sleep(delay):
        clock[0] += delay

    monkeypatch.setattr(sandbox_client_module.time, 'sleep', sleep)
    session = RecordingSession([requests.Timeout('unknown outcome'),
                                DummyResponse(201, {'snapshotID': 'original'})])
    send = session.send

    def timed_send(request, **kwargs):
        clock[0] += 1000
        return send(request, **kwargs)

    monkeypatch.setattr(session, 'send', timed_send)
    client = SandboxClient(api_key='key', session=session)
    assert client.create_snapshot('sb', 'persisted-key')['snapshotID'] == 'original'
    assert 2000 < clock[0] < 2100
    assert len(session.requests) == 2
    assert session.requests[0].body == session.requests[1].body
    assert session.requests[0].headers['Idempotency-Key'] == session.requests[1].headers['Idempotency-Key']


def test_snapshot_large_retry_count_with_zero_retry_after(monkeypatch):
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sandbox_client_module, '_monotonic_time', lambda: 0)
    failed = DummyResponse(408)
    failed.headers['Retry-After'] = '0'
    session = RecordingSession([failed] * 1100 + [
        DummyResponse(201, {'snapshotID': 'original'})])
    client = SandboxClient(api_key='key', session=session, max_retries=1100)
    assert client.create_snapshot('sb', 'persisted-key')['snapshotID'] == 'original'
    assert len(session.requests) == 1101


def test_snapshot_unknown_outcome_can_be_replayed_after_retry_exhaustion():
    session = RecordingSession([
        requests.Timeout('still processing'),
        DummyResponse(201, {'snapshotID': 'original', 'names': []}),
    ])
    client = SandboxClient(api_key='key', session=session, max_retries=0)
    with pytest.raises(SandboxError):
        client.create_snapshot('sb', 'persisted-key', memory=False)
    assert client.create_snapshot('sb', 'persisted-key', memory=False) == {
        'snapshotID': 'original', 'names': [],
    }
    assert session.requests[0].body == session.requests[1].body
    assert all(req.headers['Idempotency-Key'] == b'persisted-key'
               for req in session.requests)


@pytest.mark.parametrize('key', [None, '', 'x' * 129, 123])
def test_snapshot_requires_caller_owned_idempotency_key(key):
    client = SandboxClient(api_key='key', session=RecordingSession())
    with pytest.raises(SandboxError, match='idempotency_key'):
        client.create_snapshot('sb', key)
    assert client.session.requests == []


def test_snapshot_default_body_and_pagination():
    first = DummyResponse(200, [{'snapshotID': 'snap-1', 'names': ['team/demo']}])
    first.headers['X-Next-Token'] = 'cursor&next'
    session = RecordingSession([DummyResponse(201, {'snapshotID': 'snap-1'}),
                                first, DummyResponse(200, [])])
    client = SandboxClient(api_key='key', session=session)
    client.createSandboxSnapshot('source', 'capture')
    assert body_of(session.requests[0]) == {}
    page = client.list_snapshots(sandbox_id='source/id', name='team/demo:v1', limit=1)
    assert page['items'][0]['snapshotID'] == 'snap-1'
    assert page['nextToken'] == 'cursor&next'
    last = client.listSnapshots(next_token=page['nextToken'])
    assert last == {'items': [], 'nextToken': None}
    assert session.requests[1].method == 'GET'
    assert parse_qs(urlparse(session.requests[1].url).query) == {
        'sandboxID': ['source/id'], 'name': ['team/demo:v1'], 'limit': ['1'],
    }
    assert parse_qs(urlparse(session.requests[2].url).query) == {
        'nextToken': ['cursor&next'],
    }


def test_list_template_tags_returns_assignments_and_encodes_path():
    tags = [{'tag': 'v1', 'buildID': 'build-1', 'createdAt': '2026-11-12T00:00:00Z'}]
    session = RecordingSession([DummyResponse(200, tags)])
    client = SandboxClient(api_key='key', session=session)
    assert client.listTemplateTags('template/id') == tags
    assert session.requests[0].method == 'GET'
    assert session.requests[0].url == DEFAULT_ENDPOINT + '/templates/template%2Fid/tags'


@pytest.mark.parametrize('operation', ['create', 'replace', 'rule', 'update_rule'])
def test_http_body_injections_are_serialized_for_all_write_apis(operation):
    session = RecordingSession()
    client = SandboxClient(api_key='key', access_key='ak', secret_key='sk',
                           session=session)
    injection = {'type': 'http', 'baseUrl': 'https://api.example.com/v1/*',
                 'ifBody': {'model': 'demo'}, 'body': {'api_key': 'secret'}}
    expected = {'type': 'http', 'base_url': 'https://api.example.com/v1/*',
                'if_body': {'model': 'demo'}, 'body': {'api_key': 'secret'}}
    if operation == 'create':
        client.create_sandbox(injections=[injection])
    elif operation == 'replace':
        client.update_sandbox_injections('sb', [injection])
    elif operation == 'rule':
        client.create_injection_rule(name='demo', injection=injection)
    else:
        client.update_injection_rule('rule', injection=injection)
    body = body_of(session.requests[0])
    assert body.get('injection', (body.get('injections') or [None])[0]) == expected
    assert injection['ifBody'] == {'model': 'demo'}


@pytest.mark.parametrize('key', ['x' * 128, b'capture-bytes'])
def test_snapshot_accepts_boundary_and_bytes_idempotency_keys(key):
    session = RecordingSession()
    client = SandboxClient(api_key='key', session=session)
    client.create_snapshot('sb', key)
    expected_key = key if isinstance(key, bytes) else key.encode('utf-8')
    assert session.requests[0].headers['Idempotency-Key'] == expected_key


@pytest.fixture
def snapshot_http_server():
    received = []
    responses = []

    class Handler(StreamRequestHandler):
        def handle(self):
            # Parse CRLF-delimited bytes: legacy HTTPServer treats UTF-8 NEL
            # bytes as a Unicode line break after decoding header values.
            path = self.rfile.readline().split(b' ')[1]
            headers = {}
            while True:
                line = self.rfile.readline()
                if line in (b'\r\n', b''):
                    break
                name, value = line.rstrip(b'\r\n').split(b':', 1)
                headers[name.lower()] = value.strip()
            body = self.rfile.read(int(headers[b'content-length']))
            received.append((path, headers[b'idempotency-key'], body))
            self.wfile.write(responses.pop(0))

    server = TCPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.01))
    thread.daemon = True
    thread.start()
    session = requests.Session()
    session.trust_env = False
    try:
        yield ('http://127.0.0.1:{0}'.format(server.server_address[1]),
               session, received, responses)
    finally:
        session.close()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def snapshot_http_response(status):
    body = b'{"snapshotID":"snapshot-1","names":[]}'
    return (b'HTTP/1.1 ' + status + b'\r\nContent-Type: application/json\r\n'
            b'Content-Length: ' + str(len(body)).encode('ascii') +
            b'\r\nConnection: close\r\n\r\n' + body)


@pytest.mark.parametrize('key', [u'快照-1', u'caf\u00e9', b'capture-bytes'])
def test_snapshot_sends_utf8_idempotency_key_over_http(
        monkeypatch, key, snapshot_http_server):
    endpoint, session, received, responses = snapshot_http_server
    responses.extend([snapshot_http_response(b'408 Request Timeout'),
                      snapshot_http_response(b'201 Created')])
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    client = SandboxClient(endpoint=endpoint, api_key='key', session=session,
                           timeout=2, max_retries=1)
    result = client.create_snapshot('sb', key, memory=False)
    assert result['snapshotID'] == 'snapshot-1'
    expected_key = key if isinstance(key, bytes) else key.encode('utf-8')
    assert len(received) == 2
    for path, header, body in received:
        assert path == b'/sandboxes/sb/snapshots'
        assert header == expected_key
        assert json.loads(body.decode('utf-8')) == {'memory': False}


def test_snapshot_retries_interrupted_http_response(monkeypatch, snapshot_http_server):
    endpoint, session, received, responses = snapshot_http_server
    responses.extend([
        b'HTTP/1.1 201 Created\r\nTransfer-Encoding: chunked\r\n'
        b'Connection: close\r\n\r\n20\r\n{"snapshotID":',
        snapshot_http_response(b'201 Created'),
    ])
    monkeypatch.setattr(sandbox_client_module.time, 'sleep', lambda _: None)
    client = SandboxClient(endpoint=endpoint, api_key='key', session=session,
                           timeout=2, max_retries=1)
    assert client.create_snapshot('sb', 'capture', memory=False)['snapshotID'] == 'snapshot-1'
    assert len(received) == 2
    assert received[0] == received[1]
    assert received[0][1] == b'capture'
    assert json.loads(received[0][2].decode('utf-8')) == {'memory': False}


@pytest.mark.parametrize('method,args', [
    ('create_sandbox_snapshot', ('', 'key')),
    ('list_template_tags', ('',)),
])
def test_new_control_methods_require_identifiers(method, args):
    client = SandboxClient(api_key='key', session=RecordingSession())
    with pytest.raises(SandboxError):
        getattr(client, method)(*args)
    assert client.session.requests == []
