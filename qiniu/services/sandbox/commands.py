# -*- coding: utf-8 -*-
import base64
import binascii

from qiniu.compat import basestring

from .envd import connect_rpc, connect_stream_rpc
from .errors import CommandExitError, SandboxError


class ProcessInfo(object):
    def __init__(self, pid=None, tag=None, cmd=None, args=None, envs=None,
                 cwd=None):
        self.pid = pid
        self.tag = tag
        self.cmd = cmd
        self.args = args or []
        self.envs = envs or {}
        self.cwd = cwd

    def to_dict(self):
        return {
            'pid': self.pid,
            'tag': self.tag,
            'cmd': self.cmd,
            'args': self.args,
            'envs': self.envs,
            'cwd': self.cwd,
        }


class CommandResult(object):
    def __init__(self, pid=0, exit_code=0, stdout='', stderr='', error=''):
        self.pid = pid
        self.exit_code = exit_code
        self.exitCode = exit_code
        self.stdout = stdout or ''
        self.stderr = stderr or ''
        self.error = error or ''

    def to_dict(self):
        return {
            'pid': self.pid,
            'exitCode': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'error': self.error,
        }


def _decode_bytes(value):
    if value is None:
        return ''
    if isinstance(value, list):
        return bytearray(value).decode('utf-8', 'replace')
    if isinstance(value, basestring):
        try:
            return base64.b64decode(value).decode('utf-8', 'replace')
        except (binascii.Error, TypeError):
            return value
    return str(value)


def command_result_from_events(events, on_stdout=None, on_stderr=None,
                               on_pty=None):
    pid = 0
    stdout = ''
    stderr = ''
    exit_code = -1
    error = ''
    for raw in events or []:
        event = raw.get('event', raw) if isinstance(raw, dict) else {}
        start = event.get('start')
        data = event.get('data')
        end = event.get('end')
        if start:
            pid = start.get('pid') or pid
        if data:
            stdout_chunk = _decode_bytes(data.get('stdout'))
            stderr_chunk = _decode_bytes(data.get('stderr'))
            pty_chunk = _decode_bytes(data.get('pty'))
            if stdout_chunk and on_stdout:
                on_stdout(stdout_chunk)
            if stderr_chunk and on_stderr:
                on_stderr(stderr_chunk)
            if pty_chunk and on_pty:
                on_pty(pty_chunk)
            stdout += stdout_chunk
            stderr += stderr_chunk
            stdout += pty_chunk
        if end:
            exit_code = 0 if end.get(
                'exitCode') is None else end.get('exitCode')
            error = end.get('error') or ''
    return CommandResult(pid, exit_code, stdout, stderr, error)


class CommandHandle(object):
    def __init__(self, commands, result=None, throw_on_error=False,
                 events=None, on_stdout=None, on_stderr=None):
        self.commands = commands
        result = result or CommandResult()
        self.result = result
        self.pid = result.pid
        self.exit_code = result.exit_code
        self.exitCode = result.exit_code
        self.stdout = result.stdout
        self.stderr = result.stderr
        self.throw_on_error = throw_on_error
        self._events = events
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr

    def wait(self, on_stdout=None, on_stderr=None):
        if self._events is not None:
            result = command_result_from_events(
                self._events,
                on_stdout=on_stdout or self._on_stdout,
                on_stderr=on_stderr or self._on_stderr,
            )
            if not result.pid:
                result.pid = self.pid
            result.stdout = self.result.stdout + result.stdout
            result.stderr = self.result.stderr + result.stderr
            if not result.error:
                result.error = self.result.error
            self.result = result
            self.pid = result.pid
            self.exit_code = result.exit_code
            self.exitCode = result.exit_code
            self.stdout = result.stdout
            self.stderr = result.stderr
            self._events = None
        if self.throw_on_error and self.result.exit_code:
            raise CommandExitError(self.result)
        return self.result

    def kill(self):
        return self.commands.kill(self.pid)


class Commands(object):
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def run(self, cmd, cwd=None, envs=None, user=None, stdin=False,
            tag=None, background=False, throw_on_error=False,
            timeout=None, request_timeout=None, on_stdout=None,
            on_stderr=None, **opts):
        handle = self.start(
            cmd,
            cwd=cwd,
            envs=envs,
            user=user,
            stdin=stdin,
            tag=tag,
            throw_on_error=throw_on_error,
            timeout=(
                request_timeout if request_timeout is not None else timeout
            ),
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            **opts
        )
        return handle if background else handle.wait()

    def start(self, cmd, cwd=None, envs=None, user=None, stdin=False,
              tag=None, throw_on_error=False, timeout=None, on_stdout=None,
              on_stderr=None, **opts):
        process = {
            'cmd': '/bin/bash',
            'args': ['-l', '-c', cmd],
        }
        if cwd:
            process['cwd'] = cwd
        if envs:
            process['envs'] = envs
        body = {
            'process': process,
            'stdin': stdin,
        }
        if tag:
            body['tag'] = tag
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
            first_event = next(events)
        except StopIteration:
            first_event = None
        result = command_result_from_events(
            [first_event] if first_event else [],
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )
        return CommandHandle(
            self,
            result,
            throw_on_error=throw_on_error,
            events=events,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )

    def list(self, user=None, timeout=None):
        data = connect_rpc(
            self.sandbox,
            '/process.Process/List',
            {},
            user=user,
            timeout=timeout)
        processes = data.get('processes', []) if isinstance(data, dict) else []
        result = []
        for process in processes:
            config = process.get('config') or {}
            result.append(ProcessInfo(
                pid=process.get('pid'),
                tag=process.get('tag'),
                cmd=config.get('cmd'),
                args=config.get('args'),
                envs=config.get('envs'),
                cwd=config.get('cwd'),
            ))
        return result

    def connect(self, pid, tag=None, user=None, timeout=None,
                throw_on_error=False):
        selector = {'pid': pid}
        if tag is not None:
            selector = {'tag': tag}
        events = connect_stream_rpc(
            self.sandbox,
            '/process.Process/Connect',
            {'process': {'selector': selector}},
            user=user,
            timeout=timeout,
            stream=True,
        )
        events = iter(events)
        try:
            first_event = next(events)
        except StopIteration:
            first_event = None
        result = command_result_from_events([first_event])
        return CommandHandle(
            self,
            result,
            events=events,
            throw_on_error=throw_on_error,
        )

    def send_stdin(self, pid, data, user=None, timeout=None):
        if not isinstance(data, bytes):
            if hasattr(data, 'encode'):
                data = data.encode('utf-8')
            else:
                data = str(data).encode('utf-8')
        return connect_rpc(self.sandbox, '/process.Process/SendInput', {
            'process': {'selector': {'pid': pid}},
            'input': {'stdin': base64.b64encode(data).decode('ascii')},
        }, user=user, timeout=timeout)

    sendStdin = send_stdin

    def close_stdin(self, pid, user=None, timeout=None):
        return connect_rpc(self.sandbox, '/process.Process/CloseStdin', {
            'process': {'selector': {'pid': pid}},
        }, user=user, timeout=timeout)

    closeStdin = close_stdin

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
