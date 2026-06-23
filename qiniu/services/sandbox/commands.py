# -*- coding: utf-8 -*-
import base64

from .envd import connect_rpc, connect_stream_rpc
from .errors import CommandExitError


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
        return bytearray(value).decode('utf-8')
    if isinstance(value, str):
        try:
            return base64.b64decode(value).decode('utf-8')
        except Exception:
            return value
    return str(value)


def command_result_from_events(events):
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
            stdout += _decode_bytes(data.get('stdout'))
            stderr += _decode_bytes(data.get('stderr'))
        if end:
            exit_code = 0 if end.get(
                'exitCode') is None else end.get('exitCode')
            error = end.get('error') or ''
    return CommandResult(pid, exit_code, stdout, stderr, error)


class CommandHandle(object):
    def __init__(self, commands, result, throw_on_error=False):
        self.commands = commands
        self.result = result
        self.pid = result.pid
        self.stdout = result.stdout
        self.stderr = result.stderr
        self.throw_on_error = throw_on_error

    def wait(self):
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
            timeout=None, **opts):
        handle = self.start(
            cmd,
            cwd=cwd,
            envs=envs,
            user=user,
            stdin=stdin,
            tag=tag,
            throw_on_error=throw_on_error,
            timeout=timeout,
            **opts
        )
        return handle if background else handle.wait()

    def start(self, cmd, cwd=None, envs=None, user=None, stdin=False,
              tag=None, throw_on_error=False, timeout=None, **opts):
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
        )
        result = command_result_from_events(events)
        return CommandHandle(self, result, throw_on_error=throw_on_error)

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
            result.append({
                'pid': process.get('pid'),
                'tag': process.get('tag'),
                'cmd': config.get('cmd'),
                'args': config.get('args'),
                'envs': config.get('envs'),
                'cwd': config.get('cwd'),
            })
        return result

    def send_stdin(self, pid, data, user=None, timeout=None):
        if not isinstance(data, bytes):
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
        connect_rpc(self.sandbox, '/process.Process/SendSignal', {
            'process': {'selector': {'pid': pid}},
            'signal': 'SIGNAL_SIGKILL',
        }, user=user, timeout=timeout)
        return None
