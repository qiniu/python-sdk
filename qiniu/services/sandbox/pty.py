# -*- coding: utf-8 -*-
import base64
import threading

from .commands import CommandHandle, command_result_from_events
from .envd import connect_rpc, connect_stream_rpc
from .errors import SandboxError


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
        self._reader = None
        if on_data is not None:
            self._reader = threading.Thread(target=self._read)
            self._reader.daemon = True
            self._reader.start()

    def _read(self):
        try:
            super(_PtyHandle, self).wait()
        except BaseException as err:
            self._reader_error = err
        finally:
            try:
                self.disconnect()
            except BaseException as err:
                if self._reader_error is None:
                    self._reader_error = err
            finally:
                self._done.set()

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
        self._disconnected = True
        if self._events is not None:
            close = getattr(self._events, 'close', None)
            if close is not None:
                close()
        if self._reader is None:
            self._events = None


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
