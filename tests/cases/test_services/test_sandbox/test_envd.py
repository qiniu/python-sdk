# -*- coding: utf-8 -*-
import base64
import gc
import hashlib
from io import BytesIO, StringIO
import json
import os
import posixpath
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from threading import Event, Thread, Timer

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SimpleHTTPServer import SimpleHTTPRequestHandler

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

try:
    from urllib.parse import parse_qs, urlencode, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse
    from urllib import urlencode

import pytest
import requests

from qiniu.services.sandbox import (
    CommandExitError,
    CommandResult,
    EntryInfo,
    FileType,
    FilesystemEventType,
    GitAuthException,
    Git,
    InvalidArgumentException,
    PtySize,
    Sandbox,
    SandboxClient,
    SandboxError,
)
from qiniu.services.sandbox.envd import (
    connect_rpc,
    connect_stream_rpc,
    decode_connect_envelopes,
    encode_connect_envelope,
    iter_connect_envelopes,
)
from qiniu.services.sandbox.commands import command_result_from_events
import qiniu.services.sandbox.util as sandbox_util


class DummyResponse(object):
    def __init__(self, status_code=200, body=None, raw=None,
                 content_type='application/json'):
        self.status_code = status_code
        self.content = raw if raw is not None else json.dumps(
            body or {}).encode('utf-8')
        self.text = self.content.decode('utf-8')
        self.headers = {'Content-Type': content_type}
        self.closed = False

    def json(self):
        return json.loads(self.content.decode('utf-8'))

    def iter_content(self, chunk_size=8192):
        del chunk_size
        yield self.content

    def close(self):
        self.closed = True


class EnvdSession(object):
    def __init__(self):
        self.posts = []
        self.requests = []
        self.empty_stream_paths = set()
        self.post_exception = None
        self.request_exception = None

    def post(self, url, data=None, headers=None, timeout=None, stream=False,
             allow_redirects=False):
        assert allow_redirects is False
        if self.post_exception is not None:
            raise self.post_exception
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
            'stream': stream,
        })
        if any(url.endswith(path) for path in self.empty_stream_paths):
            return DummyResponse(
                raw=b'',
                content_type='application/connect+json',
            )
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
        if self.request_exception is not None:
            raise self.request_exception
        self.requests.append({'method': method, 'url': url, 'kwargs': kwargs})
        if method == 'GET':
            response = DummyResponse(raw=b'hello')
            self.requests[-1]['response'] = response
            return response
        response = DummyResponse(body=[{
            'name': 'hello.txt',
            'type': 'FILE',
            'path': '/tmp/hello.txt',
        }])
        self.requests[-1]['response'] = response
        return response


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


def test_decode_connect_envelopes_rejects_trailing_bytes():
    raw = encode_connect_envelope({'event': {'start': {'pid': 12}}}) + b'x'

    try:
        decode_connect_envelopes(raw)
        assert False, 'expected SandboxError'
    except SandboxError as err:
        assert str(err) == 'Sandbox envd stream truncated unexpectedly'


def test_iter_connect_envelopes_closes_stream_response():
    raw = encode_connect_envelope({'event': {'start': {'pid': 12}}})
    response = DummyResponse(raw=raw, content_type='application/connect+json')

    assert list(iter_connect_envelopes(
        response.iter_content(chunk_size=8192),
        response=response,
    )) == [{'event': {'start': {'pid': 12}}}]
    assert response.closed is True


def test_command_event_decode_handles_base64_and_non_utf8_output():
    result = command_result_from_events([{
        'event': {'data': {
            'stdout': base64.b64encode(b'YWJj').decode('ascii'),
            'stderr': base64.b64encode(b'\xff\xff\xff').decode('ascii'),
        }},
    }])

    assert result.stdout == 'YWJj'
    assert result.stderr == u'\ufffd\ufffd\ufffd'


def test_command_event_decode_expects_base64_encoded_strings():
    result = command_result_from_events([{
        'event': {'data': {
            'stdout': base64.b64encode(b'test').decode('ascii'),
        }},
    }])

    assert result.stdout == 'test'


def test_command_event_decode_decodes_plain_word_base64():
    result = command_result_from_events([{
        'event': {'data': {
            'stdout': base64.b64encode(b'text').decode('ascii'),
        }},
    }])

    assert result.stdout == 'text'


def test_command_event_decode_keeps_invalid_base64_text():
    result = command_result_from_events([{
        'event': {'data': {
            'stdout': 'not base64!',
        }},
    }])

    assert result.stdout == 'not base64!'


def test_command_event_decode_keeps_unknown_exit_code():
    result = command_result_from_events([{
        'event': {'end': {}},
    }])

    assert result.exit_code == -1


def test_command_event_decode_handles_status_exit_code():
    result = command_result_from_events([{
        'event': {'end': {'exited': True, 'status': 'exit status 7'}},
    }])

    assert result.exit_code == 7


def test_command_event_decode_handles_snake_case_exit_code():
    result = command_result_from_events([{
        'event': {'end': {'exit_code': 3}},
    }])

    assert result.exit_code == 3


def test_command_event_decode_handles_bytes_values():
    result = command_result_from_events([{
        'event': {'data': {
            'stdout': base64.b64encode(b'abc'),
            'stderr': b'plain bytes',
        }},
    }])

    assert result.stdout == 'YWJj'
    assert result.stderr == 'plain bytes'


def test_connect_error_envelopes_raise_default_sandbox_error():
    empty_error = struct.pack('>BI', 2, 0)
    missing_message = (
        struct.pack('>BI', 2, len(b'{"error":{}}')) + b'{"error":{}}'
    )

    for data in (empty_error, missing_message):
        try:
            decode_connect_envelopes(data)
            assert False, 'expected SandboxError'
        except SandboxError as err:
            assert str(err) == 'Sandbox envd stream failed'

    try:
        list(iter_connect_envelopes([empty_error]))
        assert False, 'expected SandboxError'
    except SandboxError as err:
        assert str(err) == 'Sandbox envd stream failed'


def test_connect_rpc_wraps_transport_errors():
    sandbox, session = sandbox_with_envd_session()
    session.post_exception = requests.Timeout('timed out')

    with pytest.raises(SandboxError) as err:
        sandbox.commands.run('echo hello')

    assert 'Sandbox envd request failed' in str(err.value)
    assert 'timed out' in str(err.value)


def test_connect_stream_rpc_wraps_transport_errors():
    sandbox, session = sandbox_with_envd_session()
    session.post_exception = requests.ConnectionError('connection reset')

    with pytest.raises(SandboxError) as err:
        sandbox.commands.connect(12)

    assert 'Sandbox envd request failed' in str(err.value)
    assert 'connection reset' in str(err.value)


def test_raw_envd_request_wraps_transport_errors():
    sandbox, session = sandbox_with_envd_session()
    session.request_exception = requests.Timeout('timed out')

    with pytest.raises(SandboxError) as err:
        sandbox.files.read_text('/tmp/hello.txt')

    assert 'Sandbox envd request failed' in str(err.value)
    assert 'timed out' in str(err.value)


@pytest.mark.parametrize('status', [301, 302, 303, 307, 308])
@pytest.mark.parametrize('operation', [
    'read', 'read_stream', 'write', 'write_octet', 'rpc', 'stream_rpc',
])
def test_envd_redirects_never_forward_credentials(status, operation):
    class RecordingSession(requests.Session):
        def __init__(self):
            super(RecordingSession, self).__init__()
            self.responses = []

        def send(self, request, **kwargs):
            response = super(RecordingSession, self).send(request, **kwargs)
            original_close = response.close
            response.close_called = False

            def close():
                response.close_called = True
                original_close()

            response.close = close
            self.responses.append(response)
            return response

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.respond()

        def respond(self):
            self.server.received.append(
                requests.structures.CaseInsensitiveDict(self.headers.items()))
            target = getattr(self.server, 'redirect_target', None)
            body = b'redirect' if target else b'public target'
            self.send_response(status if target else 200)
            if target:
                self.send_header('Location', target)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    target = HTTPServer(('127.0.0.1', 0), Handler)
    origin = HTTPServer(('127.0.0.1', 0), Handler)
    target.received = []
    origin.received = []
    origin.redirect_target = 'http://127.0.0.1:{0}/target'.format(
        target.server_port)
    threads = []
    for server in (target, origin):
        thread = Thread(target=server.serve_forever,
                        kwargs={'poll_interval': 0.01})
        thread.daemon = True
        thread.start()
        threads.append(thread)
    session = RecordingSession()
    client = SandboxClient(api_key='api-key', session=session, timeout=2)
    sandbox = Sandbox(client=client, sandbox_id='redirect-test',
                      envd_url='http://127.0.0.1:{0}'.format(origin.server_port),
                      envdAccessToken='not-a-real-token')
    try:
        with pytest.raises(SandboxError) as failure:
            if operation == 'read':
                sandbox.files.read('/file')
            elif operation == 'read_stream':
                sandbox.files.read('/file', format='stream')
            elif operation == 'write':
                sandbox.files.write('/file', b'hello')
            elif operation == 'write_octet':
                sandbox.files.write('/file', b'hello', use_octet_stream=True)
            elif operation == 'rpc':
                connect_rpc(sandbox, '/filesystem.Filesystem/Stat', {})
            else:
                connect_stream_rpc(sandbox, '/process.Process/Start', {},
                                   stream=True)
        assert failure.value.status_code == status
        assert len(origin.received) == 1
        assert origin.received[0]['X-Access-Token'] == 'not-a-real-token'
        assert target.received == []
        assert len(session.responses) == 1
        assert session.responses[0].close_called
    finally:
        session.close()
        for server in (origin, target):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(1)


def test_filesystem_write_accepts_unicode_text():
    sandbox, session = sandbox_with_envd_session()

    sandbox.files.write('/tmp/unicode.txt', u'你好')
    sandbox.files.write('/tmp/bytes.txt', bytearray(b'abc'))
    sandbox.files.write('/tmp/text-stream.txt', StringIO(u'你好'))

    assert session.requests[0]['kwargs']['files']['file'] == (
        'unicode.txt',
        u'你好'.encode('utf-8'),
    )
    assert session.requests[1]['kwargs']['files']['file'] == (
        'bytes.txt',
        b'abc',
    )
    stream_upload = session.requests[2]['kwargs']['files']['file']
    assert stream_upload[0] == 'text-stream.txt'
    assert stream_upload[1].read() == u'你好'.encode('utf-8')
    for attr in ('seek', 'tell', 'getvalue', 'len'):
        with pytest.raises(AttributeError):
            getattr(stream_upload[1], attr)


def test_file_basename_encodes_unicode_on_python2(monkeypatch):
    monkeypatch.setattr(sandbox_util, 'is_py2', True)

    assert sandbox_util.file_basename(u'/tmp/文件.txt') == (
        u'文件.txt'.encode('utf-8'))


def test_filesystem_write_accepts_duck_typed_file_like_objects():
    class FileLike(object):
        def read(self):
            return b'hello'

    sandbox, session = sandbox_with_envd_session()
    file_like = FileLike()

    sandbox.files.write('/tmp/file-like.txt', file_like)

    assert session.requests[0]['kwargs']['files']['file'] == (
        'file-like.txt',
        file_like,
    )


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
    assert session.posts[0]['timeout'] == 30
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
    assert session.posts[0]['timeout'] == 30
    assert session.posts[0]['url'].endswith('/process.Process/Connect')
    assert session.posts[0]['data'] == {
        'process': {'selector': {'pid': 12}},
    }


def test_commands_connect_handles_empty_event_stream():
    sandbox, session = sandbox_with_envd_session()
    session.empty_stream_paths.add('/process.Process/Connect')

    handle = sandbox.commands.connect(12)
    result = handle.wait()

    assert result.pid == 0
    assert result.exit_code == -1
    assert result.stdout == ''


def test_commands_send_stdin_encodes_unicode_text():
    sandbox, session = sandbox_with_envd_session()

    sandbox.commands.send_stdin(12, u'你好')
    sandbox.commands.send_stdin(12, bytearray(b'abc'))

    raw = session.posts[0]['data']['input']['stdin']
    assert base64.b64decode(raw).decode('utf-8') == u'你好'
    raw = session.posts[1]['data']['input']['stdin']
    assert base64.b64decode(raw) == b'abc'


def test_commands_run_supports_e2b_callbacks_and_request_timeout():
    sandbox, session = sandbox_with_envd_session()
    stdout = []
    stderr = []

    result = sandbox.commands.run(
        'echo hello',
        on_stdout=stdout.append,
        on_stderr=stderr.append,
        timeout=3,
        request_timeout=7,
    )

    assert result.stdout == 'hello\n'
    assert stdout == ['hello\n']
    assert stderr == []
    assert session.posts[0]['data']['timeout'] == 3
    assert session.posts[0]['timeout'] == 7


def test_commands_run_uses_command_timeout_for_stream_request_by_default():
    sandbox, session = sandbox_with_envd_session()

    result = sandbox.commands.run('sleep 60', timeout=120)

    assert result.exit_code == 0
    assert session.posts[0]['data']['timeout'] == 120
    assert session.posts[0]['timeout'] == 120


def test_commands_run_background_returns_before_command_finishes():
    sandbox, session = sandbox_with_envd_session()

    handle = sandbox.commands.run('sleep 30', background=True)

    assert session.posts[0]['stream'] is True
    assert handle.pid == 12
    assert handle.exit_code == -1
    assert handle.stdout == ''
    assert handle.wait().stdout == 'hello\n'


def test_pty_create_send_resize_connect_and_kill_use_process_rpc():
    sandbox, session = sandbox_with_envd_session()

    handle = sandbox.pty.create(PtySize(rows=24, cols=80), cwd='/workspace')
    sandbox.pty.send_stdin(handle.pid, u'你好\n')
    sandbox.pty.send_stdin(handle.pid, bytearray(b'abc'))
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
    assert base64.b64decode(
        session.posts[1]['data']['input']['pty']
    ).decode('utf-8') == u'你好\n'
    assert session.posts[2]['url'].endswith('/process.Process/SendInput')
    assert base64.b64decode(
        session.posts[2]['data']['input']['pty']) == b'abc'
    assert session.posts[3]['url'].endswith('/process.Process/Update')
    assert session.posts[3]['data']['pty'] == {
        'size': {'rows': 30, 'cols': 100},
    }
    assert session.posts[4]['url'].endswith('/process.Process/Connect')
    assert session.posts[5]['url'].endswith('/process.Process/SendSignal')


def test_pty_create_and_connect_handle_empty_event_streams():
    sandbox, session = sandbox_with_envd_session()
    session.empty_stream_paths.add('/process.Process/Start')

    handle = sandbox.pty.create(PtySize(rows=24, cols=80))
    result = handle.wait()

    assert result.pid == 0
    assert result.exit_code == -1
    assert result.stdout == ''

    session.empty_stream_paths = set(['/process.Process/Connect'])
    connected = sandbox.pty.connect(12)

    assert connected.wait().stdout == ''


class StreamingPtyResponse(DummyResponse):
    def __init__(self):
        super(StreamingPtyResponse, self).__init__(
            raw=b'', content_type='application/connect+json')
        self.chunks = Queue()
        self.closed_event = Event()
        self.chunks.put(encode_connect_envelope(
            {'event': {'start': {'pid': 12}}}))

    def iter_content(self, chunk_size=8192):
        del chunk_size
        while True:
            chunk = self.chunks.get()
            if chunk is None:
                return
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def send(self, data):
        self.chunks.put(encode_connect_envelope({'event': {'data': {
            'pty': base64.b64encode(data).decode('ascii'),
        }}}))

    def finish(self, exit_code=0):
        self.chunks.put(encode_connect_envelope(
            {'event': {'end': {'exitCode': exit_code}}}))
        self.chunks.put(None)

    def close(self):
        self.closed = True
        self.closed_event.set()
        self.chunks.put(None)


class StreamingPtySession(EnvdSession):
    def __init__(self, responses):
        super(StreamingPtySession, self).__init__()
        self.responses = list(responses)

    def post(self, url, **opts):
        response = super(StreamingPtySession, self).post(url, **opts)
        if url.endswith(('/process.Process/Start', '/process.Process/Connect')):
            return self.responses.pop(0)
        return response


@pytest.mark.parametrize('reconnect', [False, True])
@pytest.mark.parametrize('blocked_close', [False, True])
@pytest.mark.parametrize('late_error', [False, True])
def test_pty_disconnect_releases_waiters_before_closed_reader_unwinds(
        reconnect, blocked_close, late_error):
    class DelayedCloseResponse(StreamingPtyResponse):
        def __init__(self):
            super(DelayedCloseResponse, self).__init__()
            self.reading = Event()
            self.released = Event()
            self.close_started = Event()
            self.close_released = Event()
            self.reader_unwound = Event()
            if not blocked_close:
                self.close_released.set()

        def iter_content(self, chunk_size=8192):
            try:
                for chunk in super(DelayedCloseResponse, self).iter_content(
                        chunk_size):
                    yield chunk
                    self.reading.set()
                    self.released.wait()
            finally:
                self.reader_unwound.set()

        def close(self):
            self.close_started.set()
            self.close_released.wait()
            self.closed = True
            self.closed_event.set()

    response = DelayedCloseResponse()
    response.send(b'before disconnect')
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    received = []
    available = Event()
    waited = Event()
    results = []

    def on_data(data):
        received.append(data)
        available.set()

    handle = None
    waiter = None
    try:
        if reconnect:
            handle = sandbox.pty.connect(12, on_data=on_data)
        else:
            handle = sandbox.pty.create(on_data=on_data)
        response.released.set()
        assert available.wait(1)
        response.released.clear()
        assert response.reading.wait(1)

        def wait():
            results.append(handle.wait())
            waited.set()

        waiter = Thread(target=wait)
        waiter.daemon = True
        waiter.start()
        handle.disconnect()
        assert waited.wait(1), 'wait still depends on a closed socket read'
        assert response.close_started.wait(1)
        if blocked_close:
            assert response.closed is False
        else:
            assert response.closed_event.wait(1)
        assert results[0].stdout == 'before disconnect'
        assert results[0].exit_code == -1
        assert handle.wait() is results[0]

        if late_error:
            response.chunks.put(requests.ConnectionError('late close error'))
        else:
            response.send(b'late output')
        response.released.set()
        response.close_released.set()
        assert response.reader_unwound.wait(1)
        assert response.closed_event.wait(1)
        assert handle.wait() is results[0]
        assert received == [b'before disconnect']
        assert results[0].stdout == 'before disconnect'
    finally:
        response.released.set()
        response.close_released.set()
        response.chunks.put(None)
        if handle is not None:
            handle.disconnect()
        if waiter is not None:
            waiter.join(1)


def test_pty_output_callback_can_disconnect_its_own_handle():
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    handles = []
    disconnected = Event()

    def on_data(data):
        handles[0].disconnect()
        disconnected.set()

    handle = sandbox.pty.create(on_data=on_data)
    handles.append(handle)
    try:
        response.send(b'last output')
        assert disconnected.wait(1)
        assert handle.wait().stdout == 'last output'
        assert handle.wait().exit_code == -1
        assert response.closed_event.wait(1)
    finally:
        response.close()


def test_pty_disconnect_does_not_wait_for_an_inflight_output_callback():
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    entered = Event()
    release = Event()
    returned = Event()
    detached = Event()

    def on_data(data):
        entered.set()
        release.wait()
        returned.set()
        raise ValueError('inflight callback failed after disconnect')

    handle = sandbox.pty.create(on_data=on_data)
    try:
        response.send(b'inflight output')
        assert entered.wait(1)

        def disconnect():
            handle.disconnect()
            detached.set()

        closing = Thread(target=disconnect)
        closing.daemon = True
        closing.start()
        assert detached.wait(1), 'disconnect waited for user callback code'
        assert not returned.is_set()
        assert handle.wait().stdout == 'inflight output'
    finally:
        release.set()
        response.close()
    assert returned.wait(1)
    handle._reader.join(1)
    assert not handle._reader.is_alive()
    assert handle.wait().stdout == 'inflight output'


@pytest.mark.parametrize('reconnect', [False, True])
def test_pty_callback_receives_raw_bytes_before_process_exit(reconnect):
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    received = []
    available = Event()

    def on_data(data):
        received.append(data)
        available.set()

    try:
        if reconnect:
            handle = sandbox.pty.connect(12, on_data=on_data)
        else:
            handle = sandbox.pty.create(on_data=on_data)
        response.send(b'\xff\x00hello')
        assert available.wait(1), 'PTY output was not delivered before exit'
        assert received == [b'\xff\x00hello']
        response.finish()
        assert handle.wait().stdout == u'\ufffd\x00hello'
        assert handle.wait().exit_code == 0
        assert handle.wait().exitCode == 0
    finally:
        response.close()


@pytest.mark.parametrize('reconnect', [False, True])
def test_pty_first_output_callback_error_closes_stream_before_traceback_release(
        reconnect):
    response = StreamingPtyResponse()
    response.chunks.get()
    response.send(b'first event is data')
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    error = ValueError('first output callback failed')
    retained = []

    def on_data(data):
        raise error

    try:
        try:
            if reconnect:
                sandbox.pty.connect(12, on_data=on_data)
            else:
                sandbox.pty.create(on_data=on_data)
        except ValueError:
            retained.append(sys.exc_info())
        else:
            pytest.fail('callback error was not raised')
        assert retained[0][1] is error
        gc.collect()
        assert response.closed is True
    finally:
        retained[:] = []
        response.close()


@pytest.mark.parametrize('with_callback', [False, True])
def test_pty_disconnect_closes_stream_without_killing_and_allows_reconnect(
        with_callback):
    response = StreamingPtyResponse()
    reconnected_response = StreamingPtyResponse()
    session = StreamingPtySession([response, reconnected_response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    available = Event()
    callback = (lambda data: available.set()) if with_callback else None
    handle = sandbox.pty.create(on_data=callback)
    try:
        if with_callback:
            response.send(b'before disconnect')
            assert available.wait(1)
        handle.disconnect()
        handle.disconnect()
        assert response.closed_event.wait(1)
        assert handle.wait().pid == 12
        assert handle.wait().exit_code == -1
        assert len(session.posts) == 1

        received = []
        connected = sandbox.pty.connect(handle.pid, on_data=received.append)
        reconnected_response.send(b'after reconnect')
        reconnected_response.finish()
        assert connected.wait().stdout == 'after reconnect'
        assert received == [b'after reconnect']
        assert session.posts[1]['url'].endswith('/process.Process/Connect')
        assert session.posts[1]['data']['process']['selector'] == {'pid': 12}
    finally:
        response.close()
        reconnected_response.close()


@pytest.mark.parametrize('with_callback', [False, True])
def test_pty_disconnect_with_throw_on_error_preserves_unknown_exit_status(
        with_callback):
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    received = Event()
    callback = (lambda data: received.set()) if with_callback else None
    handle = sandbox.pty.connect(12, on_data=callback, throw_on_error=True)
    try:
        if with_callback:
            response.send(b'still running')
            assert received.wait(1)
        handle.disconnect()
        for unused in range(2):
            result = handle.wait()
            assert result.pid == 12
            assert result.exit_code == -1
        assert len(session.posts) == 1
    finally:
        response.close()


@pytest.mark.parametrize('with_callback', [False, True])
def test_pty_throw_on_error_keeps_real_nonzero_exit_failure(with_callback):
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    callback = (lambda data: None) if with_callback else None
    handle = sandbox.pty.connect(12, on_data=callback, throw_on_error=True)
    try:
        response.finish(exit_code=7)
        for unused in range(2):
            with pytest.raises(CommandExitError) as caught:
                handle.wait()
            assert caught.value.result.exit_code == 7
            assert caught.value.result.exitCode == 7
            handle.disconnect()
    finally:
        response.close()


@pytest.mark.parametrize('callback_error,with_callback', [
    (False, False), (False, True), (True, True),
])
def test_pty_wait_repeats_stream_errors_and_closes_response(
        callback_error, with_callback):
    response = StreamingPtyResponse()
    session = StreamingPtySession([response])
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    error = ValueError('callback failed') if callback_error else (
        requests.ConnectionError('stream failed'))

    def on_data(data):
        if callback_error:
            raise error

    handle = sandbox.pty.create(on_data=on_data if with_callback else None)
    try:
        if callback_error:
            response.send(b'output')
        else:
            response.chunks.put(error)
        for unused in range(2):
            with pytest.raises(type(error)) as caught:
                handle.wait()
            assert caught.value is error
        assert response.closed is True
    finally:
        response.close()


@pytest.mark.parametrize('connection_close', [False, True])
def test_pty_disconnect_interrupts_a_blocked_http_read(connection_close):
    release = Event()
    connection_closed = Event()
    disconnected = Event()
    errors = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Type', 'application/connect+json')
            self.send_header('Transfer-Encoding', 'chunked')
            if connection_close:
                self.send_header('Connection', 'close')
            self.end_headers()
            frame = encode_connect_envelope({'event': {'start': {'pid': 12}}})
            self.wfile.write(('{0:x}\r\n'.format(len(frame))).encode('ascii') +
                             frame + b'\r\n')
            self.wfile.flush()
            release.wait(5)
            try:
                self.wfile.write(b'0\r\n\r\n')
            except IOError:
                pass

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    serving = Thread(target=server.serve_forever)
    serving.daemon = True
    serving.start()
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', timeout=5),
                      sandbox_id='sbx123',
                      envd_url='http://127.0.0.1:{0}'.format(server.server_port))
    handle = None
    try:
        handle = sandbox.pty.create(on_data=lambda data: None)

        def disconnect():
            try:
                handle.disconnect()
                connection_closed.set()
                handle.wait()
            except BaseException as error:
                errors.append(error)
            finally:
                disconnected.set()

        closing = Thread(target=disconnect)
        closing.daemon = True
        closing.start()
        if not disconnected.wait(1):
            frames = sys._current_frames()
            stacks = []
            for thread in (closing, handle._reader):
                frame = frames.get(thread.ident)
                if frame is not None:
                    stacks.append('{0}:\n{1}'.format(
                        thread.name, ''.join(traceback.format_stack(frame))))
            pytest.fail('disconnect blocked on an idle HTTP stream; '
                        'connection close returned: {0}\n{1}'.format(
                            connection_closed.is_set(), '\n'.join(stacks)))
        if errors:
            raise errors[0]
        assert handle.wait().exit_code == -1
    finally:
        release.set()
        if handle is not None:
            handle.disconnect()
        server.shutdown()
        server.server_close()
        serving.join(1)


@pytest.mark.parametrize('background', [False, True])
def test_git_clone_uses_temporary_credentials_and_cleans_them(background):
    sandbox, session = sandbox_with_envd_session()
    result = sandbox.git.clone(
        'https://github.com/qiniu/private.git', '/workspace/private',
        username='demo-user', password='private-token',
        envs={'CUSTOM': 'preserved'}, background=background)
    starts = [post['data']['process'] for post in session.posts
              if post['url'].endswith('/process.Process/Start')]
    clone = next(process for process in starts
                 if (process.get('envs') or {}).get('GIT_ASKPASS'))
    assert clone['args'][-1] == (
        'git -c credential.helper= clone https://github.com/qiniu/private.git /workspace/private')
    assert clone['envs']['GIT_USERNAME'] == 'demo-user'
    assert clone['envs']['GIT_PASSWORD'] == 'private-token'
    assert clone['envs']['CUSTOM'] == 'preserved'
    askpass_path = clone['envs']['GIT_ASKPASS']
    assert clone['envs']['GIT_TERMINAL_PROMPT'] == '0'
    assert all('config --global' not in process['args'][-1]
               for process in starts)
    if background:
        assert not any(post['url'].endswith('/filesystem.Filesystem/Remove')
                       for post in session.posts)
        result = result.wait()
    assert result.exit_code == 0
    removed = [post['data']['path'] for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert removed == [askpass_path, posixpath.dirname(askpass_path)]


@pytest.mark.skipif(os.name == 'nt', reason='local askpass fixture requires POSIX shell')
def test_git_temporary_credentials_do_not_enter_configured_store_helper():
    try:
        subprocess.check_output(['git', '--version'])
    except OSError:
        pytest.skip('git executable is required')
    root = tempfile.mkdtemp(prefix='qiniu-git-credentials-')
    git_home = os.path.join(root, 'home')
    os.mkdir(git_home)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith('GIT_') or key == 'SSH_ASKPASS':
            env.pop(key)
    env.update({'HOME': git_home, 'XDG_CONFIG_HOME': git_home,
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_CONFIG_GLOBAL': os.path.join(git_home, '.gitconfig'),
                'GIT_TERMINAL_PROMPT': '0',
                'NO_PROXY': '127.0.0.1,localhost',
                'no_proxy': '127.0.0.1,localhost'})
    remote = os.path.join(root, 'remote.git')
    store = os.path.join(git_home, 'credentials')
    helper = 'store --file=' + store
    subprocess.check_call(['git', 'init', '--bare', '-q', remote], env=env)
    subprocess.check_call(['git', '--git-dir=' + remote, 'update-server-info'], env=env)
    subprocess.check_call(['git', 'config', '--global', 'credential.helper', helper], env=env)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            expected = 'Basic ' + base64.b64encode(b'demo:fake-token').decode('ascii')
            if self.headers.get('Authorization') != expected:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="local"')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            SimpleHTTPRequestHandler.do_GET(self)

        def translate_path(self, path):
            return os.path.join(root, path.split('?', 1)[0].lstrip('/'))

        def log_message(self, *args):
            pass

    def local_path(value):
        return value.replace('/tmp/qiniu-git-auth', os.path.join(root, 'auth'))

    class Files(object):
        def write(self, path, data, **opts):
            with open(local_path(path), 'w') as output:
                output.write(data)

        def remove(self, path, **opts):
            path = local_path(path)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    class Commands(object):
        def __init__(self):
            self.sandbox = type('SandboxContext', (object,), {'files': Files()})()

        def run(self, command, **opts):
            process_env = dict(env)
            process_env.update(opts.get('envs') or {})
            if 'GIT_ASKPASS' in process_env:
                process_env['GIT_ASKPASS'] = local_path(process_env['GIT_ASKPASS'])
            process = subprocess.Popen(
                shlex.split(local_path(command)), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=process_env, cwd=opts.get('cwd'))
            expired = Event()

            def expire():
                expired.set()
                try:
                    process.kill()
                except OSError:
                    pass

            timer = Timer(10, expire)
            timer.daemon = True
            timer.start()
            try:
                stdout, stderr = process.communicate()
            finally:
                timer.cancel()
            assert not expired.is_set(), 'local Git command timed out'
            return CommandResult(process.pid, process.returncode,
                                 stdout.decode('utf-8', 'replace'),
                                 stderr.decode('utf-8', 'replace'))

    server = HTTPServer(('127.0.0.1', 0), Handler)
    serving = Thread(target=server.serve_forever)
    serving.daemon = True
    serving.start()
    try:
        git = Git(Commands())
        url = 'http://127.0.0.1:{0}/remote.git'.format(server.server_port)
        result = git.clone(url, os.path.join(root, 'explicit'),
                           username='demo', password='fake-token')
        assert result.exit_code == 0, result.stderr
        assert not os.path.exists(store), 'temporary credentials reached the store helper'
        assert not any(name.startswith('auth') for name in os.listdir(root))
        configured = subprocess.check_output(
            ['git', 'config', '--global', 'credential.helper'], env=env)
        assert configured.decode('utf-8').strip() == helper

        with open(store, 'w') as output:
            output.write('http://demo:fake-token@127.0.0.1:{0}\n'.format(server.server_port))
        result = git.clone(url, os.path.join(root, 'configured-helper'))
        assert result.exit_code == 0, result.stderr
    finally:
        server.shutdown()
        server.server_close()
        serving.join(1)
        shutil.rmtree(root)


@pytest.mark.parametrize('operation', ['clone', 'pull', 'push'])
@pytest.mark.parametrize('background', [False, True])
def test_git_credentials_keep_request_user_and_private_directory(
        operation, background):
    class CredentialSession(EnvdSession):
        def post(self, url, **opts):
            response = super(CredentialSession, self).post(url, **opts)
            process = self.posts[-1]['data'].get('process') or {}
            args = process.get('args') or ['']
            if args[-1] == 'git remote get-url origin':
                return DummyResponse(raw=b''.join([
                    encode_connect_envelope({'start': {'pid': 12}}),
                    encode_connect_envelope({'data': {'stdout': base64.b64encode(
                        b'https://example.test/private.git\n').decode('ascii')}}),
                    encode_connect_envelope({'end': {'exitCode': 0}}),
                ]), content_type='application/connect+json')
            return response

    def request_user(headers):
        value = headers['Authorization'].split(' ', 1)[1]
        return base64.b64decode(value).decode('ascii').split(':', 1)[0]

    session = CredentialSession()
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})
    directories = []
    for user in ('root', 'user'):
        first_post = len(session.posts)
        opts = {'user': user, 'username': 'demo', 'password': 'fake-token',
                'background': background}
        if operation == 'clone':
            result = sandbox.git.clone('https://example.test/private.git', **opts)
        else:
            result = getattr(sandbox.git, operation)(
                '/workspace/repo', remote='origin', **opts)
        upload = session.requests[-1]
        assert request_user(upload['kwargs']['headers']) == user
        assert parse_qs(urlparse(upload['url']).query)['username'] == [user]
        starts = [post for post in session.posts[first_post:]
                  if post['url'].endswith('/process.Process/Start')]
        assert all(request_user(post['headers']) == user for post in starts)
        git_process = next(post['data']['process'] for post in starts
                           if (post['data']['process'].get('envs') or {}).get('GIT_ASKPASS'))
        askpass = git_process['envs']['GIT_ASKPASS']
        directory = posixpath.dirname(askpass)
        assert directory not in directories
        directories.append(directory)
        assert any('700' in post['data']['process']['args'][-1] and
                   directory in post['data']['process']['args'][-1]
                   for post in starts)
        if background:
            assert not any(post['url'].endswith('/filesystem.Filesystem/Remove')
                           for post in session.posts[first_post:])
            result = result.wait()
        assert result.exit_code == 0
        cleanup = [post for post in session.posts[first_post:]
                   if post['url'].endswith('/filesystem.Filesystem/Remove')]
        assert directory in [post['data']['path'] for post in cleanup]
        assert all(request_user(post['headers']) == user for post in cleanup)


def test_git_background_handle_discard_cleans_credentials_as_command_user():
    sandbox, session = sandbox_with_envd_session()
    handle = sandbox.git.clone('https://example.test/private.git',
                               username='demo', password='fake-token',
                               user='root', background=True)
    assert not any(post['url'].endswith('/filesystem.Filesystem/Remove')
                   for post in session.posts)
    del handle
    gc.collect()

    cleanup = [post for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert len(cleanup) == 2
    assert cleanup[1]['data']['path'] == posixpath.dirname(cleanup[0]['data']['path'])
    assert all(post['headers']['Authorization'] == 'Basic cm9vdDo='
               for post in cleanup)


@pytest.mark.parametrize('url_method,operation,http_method', [
    ('download_url', 'read', 'GET'), ('upload_url', 'write', 'POST'),
])
def test_public_file_urls_pass_envd_signature_expiration_and_tamper_checks(
        url_method, operation, http_method):
    token = 'envd-test-token'

    class Handler(BaseHTTPRequestHandler):
        def authorize(self, expected_operation):
            query = parse_qs(urlparse(self.path).query)
            components = [query.get('path', [''])[0], expected_operation,
                          query.get('username', [''])[0], token]
            expiration = query.get('signature_expiration', [None])[0]
            if expiration is not None:
                components.append(expiration)
            payload = ':'.join(components).encode('utf-8')
            # Envd auth.go and keys/sha256.go use standard base64 without padding.
            expected = 'v1_' + base64.b64encode(
                hashlib.sha256(payload).digest()).decode('ascii').rstrip('=')
            valid = query.get('signature', [''])[0] == expected
            if expiration is not None:
                valid = valid and int(expiration) >= int(time.time())
            self.send_response(200 if valid else 401)
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            self.authorize('read')

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.authorize('write')

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    serving = Thread(target=server.serve_forever)
    serving.daemon = True
    serving.start()
    sandbox = Sandbox(sandbox_id='sbx123', envdAccessToken=token,
                      envd_url='http://127.0.0.1:{0}'.format(server.server_port))
    client = requests.Session()
    client.trust_env = False

    def status(url, method=http_method):
        response = client.request(method, url, data=b'', timeout=2)
        return response.status_code

    try:
        url = getattr(sandbox, url_method)(
            '/tmp/hello world.txt', user='root',
            signature_expiration=int(time.time()) + 300)
        assert status(url) == 200
        assert status(url, method='POST' if operation == 'read' else 'GET') == 401

        query = dict((key, values[0]) for key, values in
                     parse_qs(urlparse(url).query).items())
        for key, value in [('signature', 'v1_tampered'),
                           ('path', '/tmp/different.txt'),
                           ('username', 'different-user'),
                           ('signature_expiration', str(int(time.time()) + 600))]:
            changed = dict(query)
            changed[key] = value
            tampered = urlparse(url)._replace(query=urlencode(changed)).geturl()
            assert status(tampered) == 401

        expired = getattr(sandbox, url_method)(
            '/tmp/hello world.txt', user='root',
            signature_expiration=int(time.time()) - 1)
        assert status(expired) == 401
        no_expiration = getattr(sandbox, url_method)(
            '/tmp/hello world.txt', user='root', signature_expiration=None)
        assert status(no_expiration) == 200
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        serving.join(1)


def test_git_clone_auth_failure_removes_temporary_credentials():
    class AuthFailureSession(EnvdSession):
        def post(self, url, **opts):
            response = super(AuthFailureSession, self).post(url, **opts)
            process = self.posts[-1]['data'].get('process') or {}
            if url.endswith('/process.Process/Start') and (
                    process.get('envs') or {}).get('GIT_ASKPASS'):
                return DummyResponse(
                    raw=b''.join([
                        encode_connect_envelope({'start': {'pid': 12}}),
                        encode_connect_envelope({'data': {
                            'stderr': base64.b64encode(
                                b'fatal: Authentication failed').decode('ascii'),
                        }}),
                        encode_connect_envelope({'end': {'exitCode': 128}}),
                    ]), content_type='application/connect+json')
            return response

    session = AuthFailureSession()
    sandbox = Sandbox(client=SandboxClient(api_key='api-key', session=session),
                      info={'sandboxID': 'sbx123', 'domain': 'example.test'})

    with pytest.raises(GitAuthException):
        sandbox.git.clone('https://github.com/qiniu/private.git',
                          username='demo-user', password='private-token', user='root')

    removed = [post['data']['path'] for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert len(removed) == 2
    assert removed[1] == posixpath.dirname(removed[0])
    cleanup = [post for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert all(post['headers']['Authorization'] == 'Basic cm9vdDo='
               for post in cleanup)


@pytest.mark.parametrize('url,credentials', [
    ('https://github.com/qiniu/private.git', {'username': 'demo-user'}),
    ('https://github.com/qiniu/private.git', {'password': 'private-token'}),
    ('git@github.com:qiniu/private.git',
     {'username': 'demo-user', 'password': 'private-token'}),
])
def test_git_clone_rejects_incomplete_or_unsupported_credentials(
        url, credentials):
    sandbox, session = sandbox_with_envd_session()
    with pytest.raises(InvalidArgumentException):
        sandbox.git.clone(url, **credentials)
    assert session.posts == []


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
    assert 'Content-Type' not in session.requests[1]['kwargs']['headers']
    assert session.requests[1]['kwargs']['files']['file'] == (
        'hello.txt',
        b'hello',
    )
    assert session.posts[0]['url'].endswith('/filesystem.Filesystem/Stat')
    assert session.posts[1]['url'].endswith('/filesystem.Filesystem/ListDir')


def test_filesystem_returns_e2b_style_entry_objects_and_streams():
    sandbox, session = sandbox_with_envd_session()

    stream = sandbox.files.read('/tmp/hello.txt', format='stream')
    written = sandbox.files.write('/tmp/hello.txt', BytesIO(b'hello'))
    info = sandbox.files.stat('/tmp/hello.txt')
    entries = sandbox.files.list('/tmp')

    assert b''.join(stream) == b'hello'
    assert session.requests[0]['response'].closed is True
    assert written.name == 'hello.txt'
    assert written.path == '/tmp/hello.txt'
    assert written.type == FileType.FILE
    assert isinstance(info, EntryInfo)
    assert info.name == 'hello.txt'
    assert info.type == FileType.FILE
    assert entries[0].name == 'hello.txt'
    assert entries[0].type == FileType.FILE
    assert session.requests[0]['kwargs']['stream'] is True
    written_data = session.requests[1]['kwargs']['files']['file'][1]
    assert session.requests[1]['kwargs']['files']['file'] == (
        'hello.txt',
        written_data,
    )
    assert isinstance(written_data, BytesIO)


def test_filesystem_read_write_pass_request_timeout_to_file_requests():
    sandbox, session = sandbox_with_envd_session()

    sandbox.files.read_text('/tmp/hello.txt', timeout=3, request_timeout=7)
    sandbox.files.write('/tmp/hello.txt', 'hello', timeout=5)
    sandbox.files.write(
        '/tmp/octet.txt',
        b'hello',
        use_octet_stream=True,
        request_timeout=11,
    )

    assert session.requests[0]['kwargs']['timeout'] == 7
    assert session.requests[1]['kwargs']['timeout'] == 5
    assert session.requests[2]['kwargs']['timeout'] == 11


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


def test_filesystem_watch_dir_handle_supports_context_manager():
    sandbox, session = sandbox_with_envd_session()

    with sandbox.files.watch_dir('/tmp') as handle:
        assert handle.watcher_id == 'watch-1'

    assert handle._closed is True
    assert session.posts[1]['url'].endswith(
        '/filesystem.Filesystem/RemoveWatcher')
