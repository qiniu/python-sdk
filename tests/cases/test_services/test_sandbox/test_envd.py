# -*- coding: utf-8 -*-
import base64
import json

from qiniu.services.sandbox import Sandbox, SandboxClient
from qiniu.services.sandbox.envd import (
    decode_connect_envelopes,
    encode_connect_envelope,
)


class DummyResponse(object):
    def __init__(self, status_code=200, body=None, raw=None,
                 content_type='application/json'):
        self.status_code = status_code
        self.content = raw if raw is not None else json.dumps(
            body or {}).encode('utf-8')
        self.text = self.content.decode('utf-8')
        self.headers = {'Content-Type': content_type}

    def json(self):
        return json.loads(self.content.decode('utf-8'))


class EnvdSession(object):
    def __init__(self):
        self.posts = []
        self.requests = []

    def post(self, url, data=None, headers=None, timeout=None):
        if headers.get('Content-Type') == 'application/connect+json':
            decoded = decode_connect_envelopes(data)[0]
        else:
            decoded = json.loads(
                data.decode('utf-8') if isinstance(data, bytes) else data
            )
        self.posts.append({
            'url': url,
            'data': decoded,
            'headers': headers,
            'timeout': timeout,
        })
        if url.endswith('/process.Process/Start'):
            raw = b''.join([
                encode_connect_envelope({'event': {'start': {'pid': 12}}}),
                encode_connect_envelope({'event': {'data': {
                    'stdout': base64.b64encode(b'hello\n').decode('ascii'),
                    'stderr': base64.b64encode(b'').decode('ascii'),
                }}}),
                encode_connect_envelope({'event': {'end': {'exitCode': 0}}}),
            ])
            return DummyResponse(
                raw=raw,
                content_type='application/connect+json',
            )
        if url.endswith('/filesystem.Filesystem/Stat'):
            return DummyResponse(
                body={
                    'result': {
                        'entry': {
                            'name': 'hello.txt',
                            'type': 'FILE'}}})
        if url.endswith('/filesystem.Filesystem/ListDir'):
            return DummyResponse(
                body={'result': {'entries': [{
                    'name': 'hello.txt',
                    'type': 'FILE',
                }]}})
        return DummyResponse(body={'result': {}})

    def request(self, method, url, **kwargs):
        self.requests.append({'method': method, 'url': url, 'kwargs': kwargs})
        if method == 'GET':
            return DummyResponse(raw=b'hello')
        return DummyResponse(body={'name': 'hello.txt', 'type': 'FILE'})


def sandbox_with_envd_session():
    session = EnvdSession()
    client = SandboxClient(api_key='api-key', session=session)
    sandbox = Sandbox(client=client, info={
        'sandboxID': 'sbx123',
        'domain': 'example.test',
        'envdAccessToken': 'token',
    })
    return sandbox, session


def test_commands_run_posts_process_start_and_decodes_events():
    sandbox, session = sandbox_with_envd_session()

    result = sandbox.commands.run('echo hello', cwd='/tmp', envs={'A': 'B'})

    assert result.pid == 12
    assert result.exit_code == 0
    assert result.stdout == 'hello\n'
    assert session.posts[0]['url'].endswith('/process.Process/Start')
    assert (
        session.posts[0]['headers']['Content-Type'] ==
        'application/connect+json'
    )
    assert session.posts[0]['headers']['Authorization'] == 'Basic dXNlcjo='
    assert session.posts[0]['headers']['X-Access-Token'] == 'token'
    assert session.posts[0]['data']['process'] == {
        'cmd': '/bin/bash',
        'args': ['-l', '-c', 'echo hello'],
        'cwd': '/tmp',
        'envs': {'A': 'B'},
    }


def test_filesystem_uses_envd_rpc_and_signed_file_urls():
    sandbox, session = sandbox_with_envd_session()

    assert sandbox.files.read_text('/tmp/hello.txt') == 'hello'
    assert sandbox.files.write('/tmp/hello.txt', 'hello')['type'] == 'file'
    assert sandbox.files.stat('/tmp/hello.txt')['type'] == 'file'
    assert sandbox.files.list(
        '/tmp') == [{'name': 'hello.txt', 'type': 'file'}]

    assert session.requests[0]['method'] == 'GET'
    assert '/files?' in session.requests[0]['url']
    assert session.requests[1]['method'] == 'POST'
    assert session.requests[1]['kwargs']['headers']['Content-Type'].startswith(
        'multipart/form-data; boundary='
    )
    assert b'name="file"' in session.requests[1]['kwargs']['data']
    assert session.posts[0]['url'].endswith('/filesystem.Filesystem/Stat')
    assert session.posts[1]['url'].endswith('/filesystem.Filesystem/ListDir')
