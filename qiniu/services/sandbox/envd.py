# -*- coding: utf-8 -*-
import json
import socket
import struct
import threading

import requests

from .constants import DEFAULT_USER
from .errors import SandboxError
from .util import basic_auth


MAX_CONNECT_ENVELOPE_BYTES = 10 * 1024 * 1024


def envd_headers(sandbox, user=None, extra=None):
    headers = {
        'Authorization': basic_auth(user or DEFAULT_USER),
    }
    if sandbox.envd_access_token:
        headers['X-Access-Token'] = sandbox.envd_access_token
    if extra:
        headers.update(extra)
    return headers


def connect_rpc(sandbox, procedure, body=None, user=None, timeout=None):
    if timeout is None:
        timeout = sandbox.client.timeout
    url = sandbox.envd_url() + procedure
    headers = envd_headers(sandbox, user, {'Content-Type': 'application/json'})
    try:
        response = sandbox.client.session.post(
            url,
            data=json.dumps(body or {}, separators=(',', ':')),
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException as err:
        raise SandboxError('Sandbox envd request failed: {0}'.format(err))
    _check_envd_response(response)
    if not response.content:
        return None
    data = response.json()
    if isinstance(data, dict) and 'result' in data:
        return data.get('result')
    return data


def encode_connect_envelope(message):
    payload = json.dumps(message or {}, separators=(',', ':')).encode('utf-8')
    return struct.pack('>BI', 0, len(payload)) + payload


def decode_connect_envelopes(data):
    if not data:
        return []
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    messages = []
    offset = 0
    while offset + 5 <= len(data):
        flags, length = struct.unpack('>BI', data[offset:offset + 5])
        offset += 5
        if length > MAX_CONNECT_ENVELOPE_BYTES:
            raise SandboxError(
                'Sandbox envd stream envelope too large: {0}'.format(length)
            )
        if offset + length > len(data):
            raise SandboxError('Sandbox envd stream truncated unexpectedly')
        payload = data[offset:offset + length]
        offset += length
        if flags & 2:
            if _is_connect_end(payload):
                continue
            _raise_connect_error(payload)
        if payload:
            messages.append(json.loads(payload.decode('utf-8')))
    if offset < len(data):
        raise SandboxError('Sandbox envd stream truncated unexpectedly')
    return messages


def _raise_connect_error(payload):
    error = None
    message = 'Sandbox envd stream failed'
    if payload:
        try:
            data = json.loads(payload.decode('utf-8'))
            if isinstance(data, dict):
                error = data.get('error')
                if isinstance(error, dict) and error.get('message'):
                    message = error.get('message')
        except (TypeError, ValueError):
            pass
    raise SandboxError(message, data=error)


def _is_connect_end(payload):
    if not payload:
        return False
    try:
        data = json.loads(payload.decode('utf-8'))
    except (TypeError, ValueError):
        return False
    return data == {}


def iter_connect_envelopes(chunks, response=None):
    try:
        buffer = b''
        for chunk in chunks:
            if not chunk:
                continue
            if not isinstance(chunk, bytes):
                chunk = chunk.encode('utf-8')
            buffer += chunk
            while len(buffer) >= 5:
                flags, length = struct.unpack('>BI', buffer[:5])
                if length > MAX_CONNECT_ENVELOPE_BYTES:
                    raise SandboxError(
                        'Sandbox envd stream envelope too large: {0}'.format(
                            length)
                    )
                if len(buffer) < 5 + length:
                    break
                payload = buffer[5:5 + length]
                buffer = buffer[5 + length:]
                if flags & 2:
                    if _is_connect_end(payload):
                        continue
                    _raise_connect_error(payload)
                if payload:
                    yield json.loads(payload.decode('utf-8'))
        if buffer:
            raise SandboxError('Sandbox envd stream truncated unexpectedly')
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


class _ConnectStream(object):
    """An event iterator whose transport can be interrupted during a read."""

    def __init__(self, response):
        self._response = response
        self._chunks = response.iter_content(chunk_size=8192)
        self._events = iter_connect_envelopes(self._chunks)
        self._closed = False
        self._reading = False
        self._state_lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self._state_lock:
            if self._closed:
                raise StopIteration
            if self._reading:
                raise ValueError('Connect stream is already being read')
            self._reading = True

        try:
            event = next(self._events)
        except BaseException as err:
            if self._finish_read(terminal=True) and isinstance(err, Exception):
                raise StopIteration
            raise
        if self._finish_read():
            raise StopIteration
        return event

    next = __next__

    def _finish_read(self, terminal=False):
        with self._state_lock:
            self._reading = False
            interrupted = self._closed
            if not (terminal or interrupted):
                return False
            self._closed = True
        try:
            self._close_resources()
        except Exception:
            pass
        return interrupted

    def _close_resources(self):
        try:
            self._events.close()
            close_chunks = getattr(self._chunks, 'close', None)
            if close_chunks is not None:
                close_chunks()
        finally:
            self._response.close()

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            if self._reading:
                # Only wake the read. Closing the response here would race
                # urllib3 releasing the connection as the read unwinds.
                self._interrupt_read()
                return
        self._close_resources()

    def _interrupt_read(self):
        raw = getattr(self._response, 'raw', None)
        if getattr(raw, 'closed', False):
            return
        shutdown = getattr(raw, 'shutdown', None)
        try:
            if shutdown is not None:
                shutdown()
        except (IOError, OSError, RuntimeError, ValueError):
            shutdown = None
        if shutdown is None:
            # A closing HTTP connection can detach its socket while the
            # current response's file object still owns the active read.
            fp = getattr(getattr(raw, '_fp', None), 'fp', None)
            sock = getattr(fp, '_sock', None)
            if sock is None:
                sock = getattr(getattr(fp, 'raw', None), '_sock', None)
            try:
                if sock is not None:
                    sock.shutdown(socket.SHUT_RDWR)
            except (IOError, OSError, RuntimeError, ValueError):
                pass


def connect_stream_rpc(sandbox, procedure, body=None, user=None, timeout=None,
                       stream=False):
    if timeout is None:
        timeout = sandbox.client.timeout
    url = sandbox.envd_url() + procedure
    headers = envd_headers(sandbox, user, {
        'Content-Type': 'application/connect+json',
        'Keepalive-Ping-Interval': '50',
    })
    request_opts = {
        'data': encode_connect_envelope(body),
        'headers': headers,
        'timeout': timeout,
        'allow_redirects': False,
    }
    if stream:
        request_opts['stream'] = True
    try:
        try:
            response = sandbox.client.session.post(url, **request_opts)
        except TypeError:
            request_opts.pop('stream', None)
            response = sandbox.client.session.post(url, **request_opts)
    except requests.RequestException as err:
        raise SandboxError('Sandbox envd request failed: {0}'.format(err))
    _check_envd_response(response)

    if stream and hasattr(response, 'iter_content'):
        return _ConnectStream(response)

    content_type = response.headers.get('Content-Type', '')
    if 'application/connect+json' in content_type:
        return decode_connect_envelopes(response.content)

    if not response.content:
        return []
    data = response.json()
    if isinstance(data, dict) and 'result' in data:
        data = data.get('result')
    if isinstance(data, dict) and 'events' in data:
        return data.get('events')
    if isinstance(data, dict) and 'event' in data:
        return [data]
    return data


def raw_envd_request(sandbox, method, url, **kwargs):
    if kwargs.get('timeout') is None:
        kwargs['timeout'] = sandbox.client.timeout
    # Envd credentials and signed URLs must not be forwarded to redirect targets.
    kwargs['allow_redirects'] = False
    try:
        response = sandbox.client.session.request(method, url, **kwargs)
    except requests.RequestException as err:
        raise SandboxError('Sandbox envd request failed: {0}'.format(err))
    _check_envd_response(response)
    return response


def _check_envd_response(response):
    if response.status_code < 200 or response.status_code >= 300:
        try:
            data = response.text
        finally:
            response.close()
        raise SandboxError(
            'Sandbox envd request failed with status {0}'.format(
                response.status_code), response, data)
