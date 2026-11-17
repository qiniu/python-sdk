# -*- coding: utf-8 -*-
import base64
import threading

from .commands import CommandHandle, command_result_from_events
from .envd import connect_rpc, connect_stream_rpc
from .errors import CommandExitError, SandboxError


class PtySize(object):
    def __init__(self, rows=24, cols=80):
        self.rows = rows
        self.cols = cols

    def to_dict(self):
        return {'rows': self.rows, 'cols': self.cols}


def _normalize_size(size=None, rows=None, cols=None):
    if size is None:
        return {'rows': rows or 24, 'cols': cols or 80}
    if hasattr(size, 'to_dict'):
        data = size.to_dict()
    elif isinstance(size, dict):
        data = size
    else:
        data = {
            'rows': getattr(size, 'rows', None),
            'cols': getattr(size, 'cols', None),
        }
    return {
        'rows': data.get('rows') or rows or 24,
        'cols': data.get('cols') or cols or 80,
    }


class _PtyHandle(CommandHandle):
    def __init__(self, pty, result, events, on_data=None,
                 throw_on_error=False):
        super(_PtyHandle, self).__init__(
            pty, result, events=events, on_data=on_data,
            throw_on_error=throw_on_error)
        self._reader_error = None
        self._done = threading.Event()
        self._state_lock = threading.RLock()
        self._disconnected = False
        self._stdout_chunks = [result.stdout]
        self._stderr_chunks = [result.stderr]
        self._result_frozen = False
        self._reader = None
        self._closer = None
        if on_data is not None:
            self._reader = threading.Thread(target=self._read)
            self._reader.daemon = True
            self._reader.start()

    def _read(self):
        events = self._events
        try:
            for event in events:
                chunks = []
                part = command_result_from_events([event], on_data=chunks.append)
                with self._state_lock:
                    if self._disconnected:
                        break
                    if part.pid:
                        self.result.pid = part.pid
                        self.pid = part.pid
                    if part.stdout:
                        self._stdout_chunks.append(part.stdout)
                    if part.stderr:
                        self._stderr_chunks.append(part.stderr)
                    if part.exit_code != -1:
                        self.result.exit_code = part.exit_code
                    if part.error:
                        self.result.error = part.error
                for chunk in chunks:
                    if self._disconnected:
                        break
                    self._on_data(chunk)
        except BaseException as err:
            with self._state_lock:
                if not self._disconnected:
                    self._reader_error = err
        finally:
            try:
                self._close_stream(events)
            finally:
                with self._state_lock:
                    self._freeze_result()
                    self._events = None
                    self._done.set()

    def _close_stream(self, events):
        try:
            close = getattr(events, 'close', None)
            if close is not None:
                close()
        except BaseException as err:
            with self._state_lock:
                if not self._disconnected and self._reader_error is None:
                    self._reader_error = err

    def _freeze_result(self):
        if self._result_frozen:
            return
        self.result.stdout = ''.join(self._stdout_chunks)
        self.result.stderr = ''.join(self._stderr_chunks)
        self.stdout = self.result.stdout
        self.stderr = self.result.stderr
        self._stdout_chunks = []
        self._stderr_chunks = []
        self.exit_code = self.result.exit_code
        self.exitCode = self.result.exit_code
        self.result.exitCode = self.result.exit_code
        if (self._reader_error is None and self.throw_on_error and
                self.result.exit_code and not (
                    self._disconnected and self.result.exit_code == -1)):
            self._reader_error = CommandExitError(self.result)
        self._result_frozen = True

    def wait(self, on_stdout=None, on_stderr=None):
        if self._reader is None:
            if self._reader_error is not None:
                raise self._reader_error
            try:
                return super(_PtyHandle, self).wait(on_stdout, on_stderr)
            except BaseException as err:
                self._reader_error = err
                self.disconnect()
                raise
        if threading.current_thread() is self._reader:
            raise RuntimeError('Cannot wait for a PTY from its output callback')
        self._done.wait()
        if self._reader_error is not None:
            raise self._reader_error
        return self.result

    def disconnect(self):
        """Close this client stream without terminating the remote PTY."""
        with self._state_lock:
            if self._disconnected:
                return
            self._disconnected = True
            events = self._events
            if self._reader is not None:
                self._freeze_result()
                self._done.set()
                if events is not None:
                    self._closer = threading.Thread(
                        target=self._close_stream, args=(events,))
                    self._closer.daemon = True
                    closer = self._closer
                else:
                    closer = None
            else:
                closer = None
        if self._reader is not None:
            if closer is not None:
                closer.start()
            return
        try:
            close = getattr(events, 'close', None)
            if close is not None:
                close()
        finally:
            with self._state_lock:
                if self._reader is None:
                    self._events = None
                self._done.set()


class Pty(object):
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def create(self, size=None, user=None, cwd=None, envs=None, timeout=None,
               rows=None, cols=None, on_data=None, **opts):
        """Create a PTY; on_data receives raw bytes in a reader thread."""
        envs = dict(envs or {})
        envs.setdefault('TERM', 'xterm-256color')
        envs.setdefault('LANG', 'C.UTF-8')
        envs.setdefault('LC_ALL', 'C.UTF-8')
        process = {
            'cmd': '/bin/bash',
            'args': ['-i', '-l'],
            'envs': envs,
        }
        if cwd:
            process['cwd'] = cwd
        body = {
            'process': process,
            'pty': {'size': _normalize_size(size, rows=rows, cols=cols)},
        }
        if opts.get('tag'):
            body['tag'] = opts.get('tag')
        events = connect_stream_rpc(
            self.sandbox,
            '/process.Process/Start',
            body,
            user=user,
            timeout=timeout,
            stream=True,
        )
        events = iter(events)
        try:
            try:
                first_event = next(events)
            except StopIteration:
                first_event = None
            result = command_result_from_events([first_event], on_data=on_data)
        except BaseException:
            close = getattr(events, 'close', None)
            if close is not None:
                try:
                    close()
                except BaseException:
                    pass
            raise
        return _PtyHandle(self, result, events, on_data=on_data)

    def connect(self, pid, user=None, timeout=None, throw_on_error=False,
                on_data=None):
        """Connect to a PTY; on_data receives raw bytes in a reader thread."""
        events = connect_stream_rpc(
            self.sandbox,
            '/process.Process/Connect',
            {'process': {'selector': {'pid': pid}}},
            user=user,
            timeout=timeout,
            stream=True,
        )
        events = iter(events)
        try:
            try:
                first_event = next(events)
            except StopIteration:
                first_event = None
            result = command_result_from_events([first_event], on_data=on_data)
        except BaseException:
            close = getattr(events, 'close', None)
            if close is not None:
                try:
                    close()
                except BaseException:
                    pass
            raise
        return _PtyHandle(
            self,
            result,
            events,
            on_data=on_data,
            throw_on_error=throw_on_error,
        )

    def send_stdin(self, pid, data, user=None, timeout=None):
        if isinstance(data, bytearray):
            data = bytes(data)
        elif not isinstance(data, bytes):
            if hasattr(data, 'encode'):
                data = data.encode('utf-8')
            else:
                data = str(data).encode('utf-8')
        return connect_rpc(self.sandbox, '/process.Process/SendInput', {
            'process': {'selector': {'pid': pid}},
            'input': {'pty': base64.b64encode(data).decode('ascii')},
        }, user=user, timeout=timeout)

    sendStdin = send_stdin
    send_input = send_stdin
    sendInput = send_stdin

    def resize(self, pid, size=None, user=None, timeout=None, rows=None,
               cols=None):
        return connect_rpc(self.sandbox, '/process.Process/Update', {
            'process': {'selector': {'pid': pid}},
            'pty': {'size': _normalize_size(size, rows=rows, cols=cols)},
        }, user=user, timeout=timeout)

    def kill(self, pid, user=None, timeout=None):
        try:
            connect_rpc(self.sandbox, '/process.Process/SendSignal', {
                'process': {'selector': {'pid': pid}},
                'signal': 'SIGNAL_SIGKILL',
            }, user=user, timeout=timeout)
            return True
        except SandboxError as err:
            if err.status_code == 404:
                return False
            raise
