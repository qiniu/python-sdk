# -*- coding: utf-8 -*-
import json
import struct

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
    url = sandbox.envd_url() + procedure
    headers = envd_headers(sandbox, user, {'Content-Type': 'application/json'})
    try:
        response = sandbox.client.session.post(
            url,
            data=json.dumps(body or {}, separators=(',', ':')),
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as err:
        raise SandboxError('Sandbox envd request failed: {0}'.format(err))
    if response.status_code < 200 or response.status_code >= 300:
        raise SandboxError(
            'Sandbox envd request failed with status {0}'.format(
                response.status_code), response, response.text, )
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


def connect_stream_rpc(sandbox, procedure, body=None, user=None, timeout=None,
                       stream=False):
    url = sandbox.envd_url() + procedure
    headers = envd_headers(sandbox, user, {
        'Content-Type': 'application/connect+json',
        'Keepalive-Ping-Interval': '50',
    })
    request_opts = {
        'data': encode_connect_envelope(body),
        'headers': headers,
        'timeout': timeout,
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
    if response.status_code < 200 or response.status_code >= 300:
        raise SandboxError(
            'Sandbox envd request failed with status {0}'.format(
                response.status_code), response, response.text, )

    if stream and hasattr(response, 'iter_content'):
        return iter_connect_envelopes(
            response.iter_content(chunk_size=8192),
            response=response,
        )

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
    try:
        response = sandbox.client.session.request(method, url, **kwargs)
    except requests.RequestException as err:
        raise SandboxError('Sandbox envd request failed: {0}'.format(err))
    if response.status_code < 200 or response.status_code >= 300:
        raise SandboxError(
            'Sandbox envd request failed with status {0}'.format(
                response.status_code), response, response.text, )
    return response
