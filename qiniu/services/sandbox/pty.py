# -*- coding: utf-8 -*-
import base64

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


class Pty(object):
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def create(self, size=None, user=None, cwd=None, envs=None, timeout=None,
               rows=None, cols=None, **opts):
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
            first_event = next(events)
        except StopIteration:
            first_event = None
        result = command_result_from_events([first_event])
        return CommandHandle(self, result, events=events)

    def connect(self, pid, user=None, timeout=None, throw_on_error=False):
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
