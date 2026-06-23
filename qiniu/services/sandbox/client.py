# -*- coding: utf-8 -*-
import os
import time

import requests

from qiniu.auth import QiniuMacAuth, QiniuMacRequestsAuth

from .constants import DEFAULT_TEMPLATE
from .errors import SandboxError, TemplateBuildError
from .resources import KodoResource
from .util import (
    encode_path,
    json_dumps,
    normalize_endpoint,
    parse_json_response,
)


_UNSET = object()


def _to_dict(value):
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    return value


def _normalize_injection(injection):
    if hasattr(injection, 'to_dict'):
        injection = injection.to_dict()
    if not isinstance(injection, dict):
        return injection
    data = dict(injection)
    if 'apiKey' in data and 'api_key' not in data:
        data['api_key'] = data.pop('apiKey')
    if 'baseUrl' in data and 'base_url' not in data:
        data['base_url'] = data.pop('baseUrl')
    if 'ruleId' in data and 'ruleID' not in data:
        data['ruleID'] = data.pop('ruleId')
    return data


def _normalize_resources(resources):
    if resources is None:
        return None
    return [_to_dict(resource) for resource in resources]


def _has_kodo_resource(resources):
    for resource in resources or []:
        if isinstance(resource, KodoResource):
            return True
        data = _to_dict(resource)
        if isinstance(data, dict) and data.get('type') == 'kodo':
            return True
    return False


def _has_saved_injection_rule(injections):
    for injection in injections or []:
        data = _normalize_injection(injection)
        if not isinstance(data, dict):
            continue
        if data.get('type') == 'id':
            return True
        if data.get('ruleID') or data.get('rule_id') or data.get('id'):
            return True
    return False


def _normalize_sandbox_create_options(template=None, **opts):
    body = {'templateID': (
        opts.pop('templateID', None) or
        opts.pop('template_id', None) or
        opts.pop('template', None) or
        template or
        DEFAULT_TEMPLATE
    )}
    for key in (
        'timeout',
        'autoPause',
        'secure',
        'network',
        'metadata',
        'mcp',
    ):
        if opts.get(key) is not None:
            body[key] = opts.get(key)
    if opts.get('auto_pause') is not None:
        body['autoPause'] = opts.get('auto_pause')
    if opts.get('allow_internet_access') is not None:
        body['allow_internet_access'] = opts.get('allow_internet_access')
    if opts.get('allowInternetAccess') is not None:
        body['allow_internet_access'] = opts.get('allowInternetAccess')
    if opts.get('envs') is not None:
        body['envVars'] = opts.get('envs')
    if opts.get('envVars') is not None:
        body['envVars'] = opts.get('envVars')
    if opts.get('lifecycle') is not None:
        lifecycle = opts.get('lifecycle') or {}
        on_timeout = lifecycle.get('on_timeout') or lifecycle.get('onTimeout')
        if on_timeout == 'pause':
            body['autoPause'] = True
    if opts.get('injections') is not None:
        body['injections'] = [_normalize_injection(
            item) for item in opts.get('injections')]
    if opts.get('resources') is not None:
        body['resources'] = _normalize_resources(opts.get('resources'))
    return body


def _normalize_list_options(opts):
    opts = dict(opts or {})
    query = opts.pop('query', None) or {}
    metadata = query.get('metadata')
    if metadata:
        for key, value in metadata.items():
            opts['metadata[{0}]'.format(key)] = value
    if query.get('state') is not None:
        opts['state'] = query.get('state')
    return opts


class SandboxClient(object):
    def __init__(self, endpoint=None, api_url=None, api_key=None,
                 access_token=None, mac=None, access_key=None,
                 secret_key=None, session=None, timeout=None, **opts):
        if (access_key and not secret_key) or (secret_key and not access_key):
            raise SandboxError(
                'Both access_key and secret_key must be provided')
        self.endpoint = normalize_endpoint(endpoint or api_url)
        self.api_key = api_key or os.getenv('QINIU_SANDBOX_API_KEY')
        self.access_token = access_token or os.getenv(
            'QINIU_SANDBOX_ACCESS_TOKEN')
        self.mac = mac
        if self.mac is None and access_key and secret_key:
            self.mac = QiniuMacAuth(access_key, secret_key)
        self.session = session or requests.Session()
        self.timeout = timeout if timeout is not None else 30

    def _headers(self, auth_type=None):
        headers = {'Content-Type': 'application/json'}
        if auth_type == 'qiniu':
            return headers
        if auth_type == 'accessToken':
            if self.access_token:
                headers['Authorization'] = 'Bearer {0}'.format(
                    self.access_token)
            return headers
        if self.api_key:
            headers['X-API-Key'] = self.api_key
            headers['Authorization'] = 'Bearer {0}'.format(self.api_key)
        elif self.access_token:
            headers['Authorization'] = 'Bearer {0}'.format(self.access_token)
        return headers

    def _auth(self, auth_type=None):
        if auth_type == 'qiniu' or (
                not self.api_key and not self.access_token and self.mac):
            if not self.mac:
                raise SandboxError(
                    'Qiniu AK/SK credentials are required for this operation'
                )
            return QiniuMacRequestsAuth(self.mac)
        return None

    def _request(self, method, path, params=None, body=_UNSET,
                 auth_type=None, empty=False):
        url = self.endpoint + path
        data = None if body is _UNSET else json_dumps(body)
        headers = self._headers(auth_type)
        auth = self._auth(auth_type)
        request = requests.Request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            auth=auth,
        )
        prepared = self.session.prepare_request(request)
        response = self.session.send(prepared, timeout=self.timeout)
        if response.status_code < 200 or response.status_code >= 300:
            response_data = None
            try:
                response_data = response.json()
            except ValueError:
                response_data = getattr(response, 'text', None)
            message = 'Sandbox API request failed with status {0}'.format(
                response.status_code
            )
            if isinstance(
                    response_data,
                    dict) and response_data.get('message'):
                message += ': {0}'.format(response_data.get('message'))
            elif isinstance(response_data, str) and response_data:
                message += ': {0}'.format(response_data)
            raise SandboxError(message, response, response_data)
        if empty:
            return None
        return parse_json_response(response)

    def list_sandboxes(self, **opts):
        return self._request('GET', '/sandboxes', params=opts)

    listSandboxes = list_sandboxes

    def list_sandboxes_v2(self, **opts):
        return self._request(
            'GET',
            '/v2/sandboxes',
            params=_normalize_list_options(opts))

    listSandboxesV2 = list_sandboxes_v2
    list = list_sandboxes_v2

    def create_sandbox(self, template=None, **opts):
        body = _normalize_sandbox_create_options(template, **opts)
        auth_type = 'qiniu' if (
            _has_kodo_resource(body.get('resources')) or
            _has_saved_injection_rule(body.get('injections'))
        ) else None
        return self._request(
            'POST',
            '/sandboxes',
            body=body,
            auth_type=auth_type)

    createSandbox = create_sandbox
    create = create_sandbox

    def get_sandbox(self, sandbox_id):
        if not sandbox_id:
            raise SandboxError('sandbox_id is required')
        return self._request(
            'GET', '/sandboxes/{0}'.format(encode_path(sandbox_id)))

    getSandbox = get_sandbox
    get_info = get_sandbox
    getInfo = get_sandbox

    def delete_sandbox(self, sandbox_id):
        if not sandbox_id:
            raise SandboxError('sandbox_id is required')
        return self._request(
            'DELETE',
            '/sandboxes/{0}'.format(encode_path(sandbox_id)),
            empty=True,
        )

    deleteSandbox = delete_sandbox
    kill_sandbox = delete_sandbox
    killSandbox = delete_sandbox
    kill = delete_sandbox

    def pause_sandbox(self, sandbox_id):
        return self._request(
            'POST',
            '/sandboxes/{0}/pause'.format(encode_path(sandbox_id)),
            body={},
            empty=True,
        )

    pauseSandbox = pause_sandbox

    def resume_sandbox(self, sandbox_id, **opts):
        return self._request(
            'POST',
            '/sandboxes/{0}/resume'.format(encode_path(sandbox_id)),
            body=opts,
        )

    resumeSandbox = resume_sandbox

    def connect_sandbox(self, sandbox_id, timeout=15, **opts):
        if timeout is None:
            timeout = opts.pop('timeout', 15)
        return self._request(
            'POST',
            '/sandboxes/{0}/connect'.format(encode_path(sandbox_id)),
            body={'timeout': timeout},
        )

    connectSandbox = connect_sandbox
    connect = connect_sandbox

    def update_sandbox_timeout(self, sandbox_id, timeout=None, **opts):
        if timeout is None:
            timeout = opts.get('timeout')
        return self._request(
            'POST',
            '/sandboxes/{0}/timeout'.format(encode_path(sandbox_id)),
            body={'timeout': timeout},
            empty=True,
        )

    updateSandboxTimeout = update_sandbox_timeout
    set_timeout = update_sandbox_timeout
    setTimeout = update_sandbox_timeout

    def refresh_sandbox(self, sandbox_id, **opts):
        return self._request(
            'POST',
            '/sandboxes/{0}/refreshes'.format(encode_path(sandbox_id)),
            body=opts,
            empty=True,
        )

    refreshSandbox = refresh_sandbox

    def update_sandbox(self, sandbox_id, **opts):
        return self._request(
            'PATCH',
            '/sandboxes/{0}'.format(encode_path(sandbox_id)),
            body=opts,
        )

    updateSandbox = update_sandbox

    def get_sandbox_metrics(self, sandbox_id, **opts):
        return self._request(
            'GET',
            '/sandboxes/{0}/metrics'.format(encode_path(sandbox_id)),
            params=opts,
        )

    getSandboxMetrics = get_sandbox_metrics
    get_metrics = get_sandbox_metrics
    getMetrics = get_sandbox_metrics

    def get_sandboxes_metrics(self, sandbox_ids):
        values = sandbox_ids
        if isinstance(sandbox_ids, dict):
            values = sandbox_ids.get(
                'sandbox_ids') or sandbox_ids.get('sandboxIDs')
        if not isinstance(values, (list, tuple)):
            values = [values]
        ids = []
        for value in values:
            if isinstance(value, str):
                ids.append(value)
            elif isinstance(value, dict):
                ids.append(value.get('sandboxId') or value.get(
                    'sandboxID') or value.get('id'))
            elif hasattr(value, 'sandbox_id'):
                ids.append(value.sandbox_id)
        ids = [item for item in ids if item]
        if not ids:
            raise SandboxError('At least one sandbox ID must be provided')
        return self._request(
            'GET',
            '/sandboxes/metrics',
            params={
                'sandbox_ids': ','.join(ids)})

    getSandboxesMetrics = get_sandboxes_metrics

    def get_sandbox_logs(self, sandbox_id, **opts):
        return self._request(
            'GET',
            '/sandboxes/{0}/logs'.format(encode_path(sandbox_id)),
            params=opts,
        )

    getSandboxLogs = get_sandbox_logs
    get_logs = get_sandbox_logs
    getLogs = get_sandbox_logs

    def create_template(self, **opts):
        return self._request('POST', '/v3/templates', body=opts)

    createTemplate = create_template
    createTemplateV3 = create_template

    def create_template_v2(self, **opts):
        return self._request('POST', '/v2/templates', body=opts)

    createTemplateV2 = create_template_v2

    def list_templates(self, **opts):
        return self._request('GET', '/templates', params=opts)

    listTemplates = list_templates

    def list_default_templates(self):
        return self._request('GET', '/default-templates')

    listDefaultTemplates = list_default_templates

    def get_template(self, template_id, **opts):
        return self._request(
            'GET',
            '/templates/{0}'.format(encode_path(template_id)),
            params=opts,
        )

    getTemplate = get_template

    def delete_template(self, template_id):
        return self._request(
            'DELETE',
            '/templates/{0}'.format(encode_path(template_id)),
            empty=True,
        )

    deleteTemplate = delete_template

    def update_template(self, template_id, **opts):
        return self._request(
            'PATCH',
            '/templates/{0}'.format(encode_path(template_id)),
            body=opts,
        )

    updateTemplate = update_template

    def rebuild_template(self, template_id, **opts):
        return self._request(
            'POST',
            '/templates/{0}'.format(encode_path(template_id)),
            body=opts,
            auth_type='accessToken',
        )

    rebuildTemplate = rebuild_template

    def get_template_build_status(self, template_id, build_id, **opts):
        return self._request(
            'GET',
            '/templates/{0}/builds/{1}/status'.format(
                encode_path(template_id),
                encode_path(build_id),
            ),
            params=opts,
        )

    getTemplateBuildStatus = get_template_build_status

    def get_template_build_logs(self, template_id, build_id, **opts):
        return self._request(
            'GET',
            '/templates/{0}/builds/{1}/logs'.format(
                encode_path(template_id),
                encode_path(build_id),
            ),
            params=opts,
        )

    getTemplateBuildLogs = get_template_build_logs

    def start_template_build(self, template_id, build_id, **opts):
        return self._request(
            'POST',
            '/v2/templates/{0}/builds/{1}'.format(
                encode_path(template_id),
                encode_path(build_id),
            ),
            body=opts,
            empty=True,
        )

    startTemplateBuild = start_template_build
    startTemplateBuildV2 = start_template_build

    def assign_template_tags(self, **opts):
        return self._request('POST', '/templates/tags', body=opts)

    assignTemplateTags = assign_template_tags

    def delete_template_tags(self, **opts):
        return self._request(
            'DELETE',
            '/templates/tags',
            body=opts,
            empty=True)

    deleteTemplateTags = delete_template_tags

    def get_template_by_alias(self, alias):
        return self._request(
            'GET', '/templates/aliases/{0}'.format(encode_path(alias)))

    getTemplateByAlias = get_template_by_alias

    def list_injection_rules(self):
        return self._request('GET', '/injection-rules', auth_type='qiniu')

    listInjectionRules = list_injection_rules

    def create_injection_rule(self, **opts):
        if opts.get('injection') is not None:
            opts['injection'] = _normalize_injection(opts.get('injection'))
        return self._request(
            'POST',
            '/injection-rules',
            body=opts,
            auth_type='qiniu',
        )

    createInjectionRule = create_injection_rule

    def get_injection_rule(self, rule_id):
        return self._request(
            'GET',
            '/injection-rules/{0}'.format(encode_path(rule_id)),
            auth_type='qiniu',
        )

    getInjectionRule = get_injection_rule

    def update_injection_rule(self, rule_id, **opts):
        if opts.get('injection') is not None:
            opts['injection'] = _normalize_injection(opts.get('injection'))
        return self._request(
            'PUT',
            '/injection-rules/{0}'.format(encode_path(rule_id)),
            body=opts,
            auth_type='qiniu',
        )

    updateInjectionRule = update_injection_rule

    def delete_injection_rule(self, rule_id):
        return self._request(
            'DELETE',
            '/injection-rules/{0}'.format(encode_path(rule_id)),
            auth_type='qiniu',
            empty=True,
        )

    deleteInjectionRule = delete_injection_rule

    def wait_for_build(self, template_id, build_id, interval=1, timeout=60):
        start = time.time()
        while True:
            info = self.get_template_build_status(template_id, build_id)
            if info and info.get('status') in ('ready', 'error'):
                if info.get('status') == 'error':
                    message = (
                        (
                            isinstance(info.get('error'), dict) and
                            info.get('error').get('message')
                        ) or
                        info.get('error') or
                        info.get('message') or
                        'Sandbox template build failed'
                    )
                    raise TemplateBuildError(message, data=info)
                return info
            if time.time() - start >= timeout:
                raise SandboxError('Sandbox template build polling timed out')
            time.sleep(interval)

    waitForBuild = wait_for_build
