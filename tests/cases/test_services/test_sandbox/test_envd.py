# -*- coding: utf-8 -*-
import base64
import json

from qiniu.services.sandbox import (
    FileType,
    FilesystemEventType,
    PtySize,
    Sandbox,
    SandboxClient,
)
from qiniu.services.sandbox.envd import (
    decode_connect_envelopes,
    encode_connect_envelope,
    iter_connect_envelopes,
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
            decoded = self.posts[-1]['data']
            output_key = 'pty' if decoded.get('pty') else 'stdout'
            raw = b''.join([
                encode_connect_envelope({'event': {'start': {'pid': 12}}}),
                encode_connect_envelope({'event': {'data': {
                    output_key: base64.b64encode(b'hello\n').decode('ascii'),
                    'stderr': base64.b64encode(b'').decode('ascii'),
                }}}),
                encode_connect_envelope({'event': {'end': {'exitCode': 0}}}),
            ])
            return DummyResponse(
                raw=raw,
                content_type='application/connect+json',
            )
        if url.endswith('/process.Process/Connect'):
            raw = b''.join([
                encode_connect_envelope({'event': {'start': {'pid': 12}}}),
                encode_connect_envelope({'event': {'data': {
                    'stdout': base64.b64encode(b'connected\n').decode(
                        'ascii'),
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
        if url.endswith('/filesystem.Filesystem/CreateWatcher'):
            return DummyResponse(body={'result': {'watcherId': 'watch-1'}})
        if url.endswith('/filesystem.Filesystem/GetWatcherEvents'):
            return DummyResponse(body={'result': {'events': [{
                'name': 'hello.txt',
                'type': 'EVENT_TYPE_WRITE',
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


def test_iter_connect_envelopes_decodes_chunked_stream_frames():
    raw = b''.join([
        encode_connect_envelope({'event': {'start': {'pid': 12}}}),
        encode_connect_envelope({'event': {'data': {
            'stdout': base64.b64encode(b'hello').decode('ascii'),
        }}}),
    ])

    assert list(iter_connect_envelopes([
        raw[:3],
        raw[3:9],
        raw[9:],
    ])) == [
        {'event': {'start': {'pid': 12}}},
        {'event': {'data': {
            'stdout': base64.b64encode(b'hello').decode('ascii'),
        }}},
    ]


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


def test_commands_connect_returns_handle_for_running_process():
    sandbox, session = sandbox_with_envd_session()

    handle = sandbox.commands.connect(12)
    result = handle.wait()

    assert result.pid == 12
    assert result.stdout == 'connected\n'
    assert session.posts[0]['url'].endswith('/process.Process/Connect')
    assert session.posts[0]['data'] == {
        'process': {'selector': {'pid': 12}},
    }


def test_commands_run_supports_e2b_callbacks_and_request_timeout():
    sandbox, session = sandbox_with_envd_session()
    stdout = []
    stderr = []

    result = sandbox.commands.run(
        'echo hello',
        on_stdout=stdout.append,
        on_stderr=stderr.append,
        request_timeout=7,
    )

    assert result.stdout == 'hello\n'
    assert stdout == ['hello\n']
    assert stderr == []
    assert session.posts[0]['timeout'] == 7


def test_pty_create_send_resize_connect_and_kill_use_process_rpc():
    sandbox, session = sandbox_with_envd_session()

    handle = sandbox.pty.create(PtySize(rows=24, cols=80), cwd='/workspace')
    sandbox.pty.send_stdin(handle.pid, 'ls\n')
    sandbox.pty.resize(handle.pid, {'rows': 30, 'cols': 100})
    connected = sandbox.pty.connect(handle.pid)
    assert sandbox.pty.kill(handle.pid) is True

    assert handle.wait().stdout == 'hello\n'
    assert connected.wait().stdout == 'connected\n'
    assert session.posts[0]['url'].endswith('/process.Process/Start')
    assert session.posts[0]['data']['process']['args'] == ['-i', '-l']
    assert session.posts[0]['data']['process']['cwd'] == '/workspace'
    assert session.posts[0]['data']['process']['envs']['TERM'] == (
        'xterm-256color')
    assert session.posts[0]['data']['pty'] == {
        'size': {'rows': 24, 'cols': 80},
    }
    assert session.posts[1]['url'].endswith('/process.Process/SendInput')
    assert session.posts[1]['data']['input']['pty']
    assert session.posts[2]['url'].endswith('/process.Process/Update')
    assert session.posts[2]['data']['pty'] == {
        'size': {'rows': 30, 'cols': 100},
    }
    assert session.posts[3]['url'].endswith('/process.Process/Connect')
    assert session.posts[4]['url'].endswith('/process.Process/SendSignal')


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


def test_filesystem_write_files_accepts_e2b_style_file_list():
    sandbox, session = sandbox_with_envd_session()

    result = sandbox.files.write_files([
        {'path': '/tmp/a.txt', 'data': 'a'},
        {'path': '/tmp/b.txt', 'data': b'b'},
    ])

    assert [entry['type'] for entry in result] == ['file', 'file']
    assert session.requests[0]['method'] == 'POST'
    assert session.requests[1]['method'] == 'POST'


def test_filesystem_watch_dir_returns_e2b_style_watch_handle():
    sandbox, session = sandbox_with_envd_session()

    handle = sandbox.files.watch_dir('/tmp', recursive=True)
    events = handle.get_new_events()
    handle.stop()

    assert handle.watcher_id == 'watch-1'
    assert events[0].name == 'hello.txt'
    assert events[0].type == FilesystemEventType.WRITE
    assert FileType.FILE == 'file'
    assert session.posts[0]['url'].endswith(
        '/filesystem.Filesystem/CreateWatcher')
    assert session.posts[0]['data'] == {'path': '/tmp', 'recursive': True}
    assert session.posts[1]['url'].endswith(
        '/filesystem.Filesystem/GetWatcherEvents')
    assert session.posts[1]['data'] == {'watcherId': 'watch-1'}
    assert session.posts[2]['url'].endswith(
        '/filesystem.Filesystem/RemoveWatcher')
