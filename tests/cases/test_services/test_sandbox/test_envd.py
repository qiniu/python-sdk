# -*- coding: utf-8 -*-
import base64
import gc
from io import BytesIO, StringIO
import json
import struct
import sys
from threading import Event, Thread

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import pytest
import requests

from qiniu.services.sandbox import (
    CommandExitError,
    EntryInfo,
    FileType,
    FilesystemEventType,
    GitAuthException,
    InvalidArgumentException,
    PtySize,
    Sandbox,
    SandboxClient,
    SandboxError,
)
from qiniu.services.sandbox.envd import (
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

    def post(self, url, data=None, headers=None, timeout=None, stream=False):
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
        assert response.closed is True
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


def test_pty_disconnect_interrupts_a_blocked_http_read():
    release = Event()
    disconnected = Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Type', 'application/connect+json')
            self.send_header('Transfer-Encoding', 'chunked')
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
            handle.disconnect()
            handle.wait()
            disconnected.set()

        closing = Thread(target=disconnect)
        closing.daemon = True
        closing.start()
        assert disconnected.wait(1), 'disconnect blocked on an idle HTTP stream'
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
                 if process['args'][-1].startswith('git clone '))
    assert clone['args'][-1] == (
        'git clone https://github.com/qiniu/private.git /workspace/private')
    assert clone['envs']['GIT_USERNAME'] == 'demo-user'
    assert clone['envs']['GIT_PASSWORD'] == 'private-token'
    assert clone['envs']['CUSTOM'] == 'preserved'
    askpass_path = clone['envs']['GIT_ASKPASS']
    assert clone['envs']['GIT_TERMINAL_PROMPT'] == '0'
    assert all('credential.helper' not in process['args'][-1]
               for process in starts)
    if background:
        assert not any(post['url'].endswith('/filesystem.Filesystem/Remove')
                       for post in session.posts)
        result = result.wait()
    assert result.exit_code == 0
    removed = [post['data']['path'] for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert removed == [askpass_path]


def test_git_clone_auth_failure_removes_temporary_credentials():
    class AuthFailureSession(EnvdSession):
        def post(self, url, **opts):
            response = super(AuthFailureSession, self).post(url, **opts)
            process = self.posts[-1]['data'].get('process') or {}
            args = process.get('args') or []
            if url.endswith('/process.Process/Start') and args[-1].startswith(
                    'git clone '):
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
                          username='demo-user', password='private-token')

    removed = [post['data']['path'] for post in session.posts
               if post['url'].endswith('/filesystem.Filesystem/Remove')]
    assert len(removed) == 1


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
