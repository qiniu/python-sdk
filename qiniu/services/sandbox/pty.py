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
        self._done = False
        self._state = threading.Condition()
        self._callback_waiter = None
        self._pending_callback = None
        self._disconnected = False
        self._stdout_chunks = [result.stdout]
        self._stderr_chunks = [result.stderr]
        self._result_frozen = False
        self._reader = None
        self._closer = None
        if on_data is not None:
            self._start_reader()

    def _start_reader(self, on_stdout=None, on_stderr=None):
        self._reader = threading.Thread(
            target=self._read, args=(self._events, on_stdout, on_stderr))
        self._reader.daemon = True
        self._reader.start()

    def _read(self, events, on_stdout, on_stderr):
        try:
            for event in events:
                callbacks = []
                part = command_result_from_events(
                    [event],
                    on_stdout=(lambda data: callbacks.append((on_stdout, data)))
                    if on_stdout is not None else None,
                    on_stderr=(lambda data: callbacks.append((on_stderr, data)))
                    if on_stderr is not None else None,
                    on_data=(lambda data: callbacks.append((self._on_data, data)))
                    if self._on_data is not None else None,
                )
                with self._state:
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
                for callback, chunk in callbacks:
                    with self._state:
                        if self._disconnected:
                            break
                        if self._callback_waiter is not None:
                            # One callback at a time, on the first waiter's thread.
                            self._pending_callback = (callback, chunk)
                            self._state.notify_all()
                            while self._pending_callback is not None:
                                self._state.wait()
                            if self._reader_error is not None:
                                break
                            continue
                        # Dispatch is committed here; user code runs unlocked.
                    callback(chunk)
                with self._state:
                    if self._disconnected or self._reader_error is not None:
                        break
        except BaseException as err:
            with self._state:
                if not self._disconnected:
                    self._reader_error = err
        finally:
            try:
                self._close_stream(events)
            finally:
                with self._state:
                    self._freeze_result()
                    self._events = None
                    self._done = True
                    self._state.notify_all()

    def _close_stream(self, events):
        try:
            close = getattr(events, 'close', None)
            if close is not None:
                close()
        except BaseException as err:
            with self._state:
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
        current = threading.current_thread()
        with self._state:
            if not self._done:
                if self._reader is None:
                    if on_stdout is not None or on_stderr is not None:
                        self._callback_waiter = current
                    self._start_reader(on_stdout, on_stderr)
                elif current in (self._reader, self._callback_waiter):
                    raise RuntimeError(
                        'Cannot wait for a PTY from its output callback')

            dispatch_callbacks = self._callback_waiter is current
        try:
            return self._wait_for_result(dispatch_callbacks)
        except BaseException:
            with self._state:
                interrupted_dispatch = dispatch_callbacks and not self._done
            if interrupted_dispatch:
                # No waiter remains to acknowledge the reader's callbacks.
                self.disconnect()
            raise

    def _wait_for_result(self, dispatch_callbacks):
        while True:
            with self._state:
                if self._done:
                    if self._reader_error is not None:
                        raise self._reader_error
                    return self.result
                if not dispatch_callbacks or self._pending_callback is None:
                    self._state.wait()
                    continue
                callback, chunk = self._pending_callback

            error = None
            try:
                callback(chunk)
            except BaseException as err:
                error = err
            with self._state:
                if not self._disconnected and error is not None:
                    self._reader_error = error
                self._pending_callback = None
                self._state.notify_all()

    def disconnect(self):
        """Detach immediately; already-dispatched callbacks may still run."""
        with self._state:
            if self._disconnected:
                return
            self._disconnected = True
            events = self._events
            self._events = None
            self._freeze_result()
            self._pending_callback = None
            self._done = True
            self._state.notify_all()
            if events is not None:
                self._closer = threading.Thread(
                    target=self._close_stream, args=(events,))
                self._closer.daemon = True
                closer = self._closer
            else:
                closer = None
        if closer is not None:
            closer.start()


class Pty(object):
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def create(self, size=None, user=None, cwd=None, envs=None, timeout=None,
               rows=None, cols=None, on_data=None, **opts):
        """Create a PTY and pass raw output bytes to on_data.

        Output in the first event calls on_data inline. A callback error there
        closes the stream and propagates from create(). Later events call
        on_data from the reader thread and report callback errors via wait().
        """
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
        """Connect to a PTY and pass raw output bytes to on_data.

        Output in the first event calls on_data inline. A callback error there
        closes the stream and propagates from connect(). Later events call
        on_data from the reader thread and report callback errors via wait().
        """
        events = connect_stream_rpc(
            self.sandbox,
            '/process.Process/Connect',
            {'process': {'pid': pid}},
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
            'process': {'pid': pid},
            'input': {'pty': base64.b64encode(data).decode('ascii')},
        }, user=user, timeout=timeout)

    sendStdin = send_stdin
    send_input = send_stdin
    sendInput = send_stdin

    def resize(self, pid, size=None, user=None, timeout=None, rows=None,
               cols=None):
        return connect_rpc(self.sandbox, '/process.Process/Update', {
            'process': {'pid': pid},
            'pty': {'size': _normalize_size(size, rows=rows, cols=cols)},
        }, user=user, timeout=timeout)

    def kill(self, pid, user=None, timeout=None):
        try:
            connect_rpc(self.sandbox, '/process.Process/SendSignal', {
                'process': {'pid': pid},
                'signal': 'SIGNAL_SIGKILL',
            }, user=user, timeout=timeout)
            return True
        except SandboxError as err:
            if err.status_code == 404:
                return False
            raise
