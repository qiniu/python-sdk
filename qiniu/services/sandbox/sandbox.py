# -*- coding: utf-8 -*-
import time

import requests

from .client import SandboxClient
from .commands import Commands
from .constants import DEFAULT_USER, ENVD_PORT, MCP_PORT
from .errors import SandboxError
from .filesystem import Filesystem
from .git import Git
from .pty import Pty
from .util import (
    append_query,
    file_signature,
    get_info_value,
    utc_timestamp_after,
)


class _ConnectDescriptor(object):
    def __get__(self, obj, cls):
        if obj is None:
            def class_connect(sandbox_id, client=None, timeout=15, **opts):
                client = client or SandboxClient(**opts)
                info = client.connect_sandbox(sandbox_id, timeout=timeout)
                sandbox = cls(client=client, info=info, sandbox_id=sandbox_id)
                sandbox.refresh_envd_token_if_needed()
                return sandbox
            return class_connect

        def instance_connect(timeout=15, **opts):
            info = obj.client.connect_sandbox(
                obj.sandbox_id, timeout=timeout, **opts)
            obj.update_info(info)
            obj.refresh_envd_token_if_needed()
            return obj
        return instance_connect


class SandboxPaginator(object):
    def __init__(self, client=None, **opts):
        self.client = client or SandboxClient(**opts)
        self.opts = dict(opts)
        self.opts.pop('client', None)
        self.next_token = opts.get('nextToken') or opts.get('next_token')
        self.opts.pop('nextToken', None)
        self.opts.pop('next_token', None)
        self._has_next = True

    @property
    def has_next(self):
        return bool(self.next_token) or self._has_next

    hasNext = has_next

    def next_items(self, **opts):
        request_opts = dict(self.opts)
        request_opts.update(opts)
        if self.next_token and request_opts.get('nextToken') is None:
            request_opts['nextToken'] = self.next_token
        data = self.client.list_sandboxes_v2(**request_opts) or {}
        items = data if isinstance(data, list) else (
            data.get('items') or data.get('sandboxes') or []
        )
        self.next_token = None if isinstance(data, list) else (
            data.get('nextToken') or data.get('next_token')
        )
        self._has_next = bool(self.next_token)
        return [Sandbox(client=self.client, info=item) for item in items]

    nextItems = next_items


class Sandbox(object):
    connect = _ConnectDescriptor()

    def __init__(self, client=None, info=None, sandbox_id=None, sandboxID=None,
                 envd_url=None, envdAccessToken=None, **client_opts):
        self.client = client or SandboxClient(**client_opts)
        self.info = info or {}
        self.sandbox_id = (
            sandbox_id or sandboxID or
            self.info.get('sandboxID') or
            self.info.get('sandboxId') or
            self.info.get('sandbox_id') or
            self.info.get('id')
        )
        self.sandboxID = self.sandbox_id
        self.template_id = (
            self.info.get('templateID') or
            self.info.get('templateId') or
            self.info.get('template_id')
        )
        self.templateID = self.template_id
        self.domain = (
            self.info.get('domain') or
            self.info.get('sandboxDomain') or
            self.info.get('sandbox_domain')
        )
        self.sandbox_domain = self.domain
        self.sandboxDomain = self.domain
        self.envd_version = get_info_value(
            self.info, 'envdVersion', 'envd_version')
        self.envdVersion = self.envd_version
        self.envd_access_token = (
            envdAccessToken or
            get_info_value(self.info, 'envdAccessToken', 'envd_access_token')
        )
        self.envdAccessToken = self.envd_access_token
        self.traffic_access_token = get_info_value(
            self.info, 'trafficAccessToken', 'traffic_access_token'
        )
        self.trafficAccessToken = self.traffic_access_token
        self._envd_url = envd_url
        self.files = Filesystem(self)
        self.filesystem = self.files
        self.commands = Commands(self)
        self.pty = Pty(self)
        self.git = Git(self.commands)

    @classmethod
    def create(cls, template=None, client=None, timeout=None, metadata=None,
               envs=None, secure=True, allow_internet_access=True, mcp=None,
               network=None, lifecycle=None, resources=None, injections=None,
               **opts):
        client_opts = {}
        for key in ('endpoint', 'api_url', 'api_key', 'access_token',
                    'mac', 'access_key', 'secret_key', 'session'):
            if key in opts:
                client_opts[key] = opts.pop(key)
        client = client or SandboxClient(**client_opts)
        info = client.create_sandbox(
            template=template,
            timeout=timeout,
            metadata=metadata,
            envs=envs,
            secure=secure,
            allow_internet_access=allow_internet_access,
            mcp=mcp,
            network=network,
            lifecycle=lifecycle,
            resources=resources,
            injections=injections,
            **opts
        )
        sandbox = cls(client=client, info=info)
        sandbox.refresh_envd_token_if_needed()
        return sandbox

    @classmethod
    def list(cls, client=None, **opts):
        return SandboxPaginator(client=client, **opts)

    def update_info(self, info):
        if not info:
            return self
        self.info = info
        self.sandbox_id = (
            info.get('sandboxID') or info.get('sandboxId') or
            info.get('sandbox_id') or self.sandbox_id
        )
        self.sandboxID = self.sandbox_id
        self.template_id = (
            info.get('templateID') or info.get('templateId') or
            info.get('template_id') or self.template_id
        )
        self.templateID = self.template_id
        self.domain = (
            info.get('domain') or info.get('sandboxDomain') or
            info.get('sandbox_domain') or self.domain
        )
        self.sandbox_domain = self.domain
        self.sandboxDomain = self.domain
        self.envd_access_token = (
            get_info_value(info, 'envdAccessToken', 'envd_access_token') or
            self.envd_access_token
        )
        self.envdAccessToken = self.envd_access_token
        self.traffic_access_token = (
            get_info_value(
                info,
                'trafficAccessToken',
                'traffic_access_token',
            ) or self.traffic_access_token
        )
        self.trafficAccessToken = self.traffic_access_token
        self.envd_version = (
            get_info_value(info, 'envdVersion', 'envd_version') or
            self.envd_version
        )
        self.envdVersion = self.envd_version
        return self

    updateInfo = update_info

    def refresh_envd_token_if_needed(self):
        if self.envd_access_token or not self.sandbox_id:
            return self
        try:
            self.update_info(self.get_info())
        except SandboxError:
            pass
        return self

    refreshEnvdTokenIfNeeded = refresh_envd_token_if_needed

    def kill(self):
        return self.client.delete_sandbox(self.sandbox_id)

    def set_timeout(self, timeout):
        return self.client.update_sandbox_timeout(
            self.sandbox_id, timeout=timeout)

    setTimeout = set_timeout

    def refresh(self, duration=None, **opts):
        if duration is not None:
            opts['duration'] = duration
        return self.client.refresh_sandbox(self.sandbox_id, **opts)

    def pause(self):
        return self.client.pause_sandbox(self.sandbox_id)

    beta_pause = pause
    betaPause = pause

    def resume(self, **opts):
        info = self.client.resume_sandbox(self.sandbox_id, **opts)
        self.update_info(info)
        return self

    def update_network(self, network):
        return self.client.update_sandbox(self.sandbox_id, network=network)

    updateNetwork = update_network

    def get_info(self):
        return self.client.get_sandbox(self.sandbox_id)

    getInfo = get_info

    def get_metrics(self, **opts):
        return self.client.get_sandbox_metrics(self.sandbox_id, **opts)

    getMetrics = get_metrics

    def get_logs(self, **opts):
        return self.client.get_sandbox_logs(self.sandbox_id, **opts)

    getLogs = get_logs

    def get_host(self, port):
        if not self.domain:
            return ''
        return '{0}-{1}.{2}'.format(port, self.sandbox_id, self.domain)

    getHost = get_host

    def envd_url(self):
        if self._envd_url:
            return self._envd_url
        return 'https://{0}'.format(self.get_host(ENVD_PORT))

    envdUrl = envd_url

    def get_mcp_url(self):
        return 'https://{0}/mcp'.format(self.get_host(MCP_PORT))

    getMcpUrl = get_mcp_url

    def get_mcp_token(self):
        return self.traffic_access_token

    getMcpToken = get_mcp_token

    def file_url(
            self,
            path,
            operation,
            user=None,
            signature_expiration=300,
            **opts):
        user = user or DEFAULT_USER
        query = {
            'path': path,
            'username': user,
        }
        if self.envd_access_token:
            expiration = opts.get('signatureExpiration', signature_expiration)
            if expiration < 1000000000:
                expiration = utc_timestamp_after(expiration)
            query['signature'] = file_signature(
                path,
                operation,
                user,
                self.envd_access_token,
                expiration,
            )
            query['signature_expiration'] = expiration
        return self.envd_url() + append_query('/files', query)

    fileUrl = file_url

    def download_url(self, path, **opts):
        return self.file_url(path, 'read', **opts)

    downloadUrl = download_url
    DownloadURL = download_url

    def upload_url(self, path, **opts):
        return self.file_url(path, 'write', **opts)

    uploadUrl = upload_url
    UploadURL = upload_url

    def wait_for_ready(self, timeout=60, interval=1):
        started = time.time()
        while True:
            elapsed = time.time() - started
            remaining = None if timeout is None else max(timeout - elapsed, 0)
            request_timeout = interval
            if remaining is not None:
                request_timeout = min(interval, remaining)
            try:
                response = self.client.session.get(
                    self.envd_url() + '/health',
                    timeout=request_timeout,
                )
                if response.status_code >= 200 and response.status_code < 300:
                    return self
            except requests.RequestException:
                pass
            if timeout is not None and time.time() - started >= timeout:
                raise SandboxError('Sandbox envd did not become ready')
            time.sleep(interval)

    waitForReady = wait_for_ready

    def is_running(self, request_timeout=None):
        response = self.client.session.get(
            self.envd_url() + '/health',
            timeout=request_timeout,
        )
        if response.status_code == 502:
            return False
        if response.status_code >= 200 and response.status_code < 300:
            return True
        return False

    isRunning = is_running
