# -*- coding: utf-8 -*-
import os
import time

import requests

from qiniu.auth import QiniuMacAuth, QiniuMacRequestsAuth
from qiniu.compat import (
    basestring,
    bytes as bytes_type,
    str as text_type,
    urlencode,
)

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


try:
    from time import monotonic as _monotonic_time
except ImportError:
    _monotonic_time = time.time


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
    if 'ifHeaders' in data and 'if_headers' not in data:
        data['if_headers'] = data.pop('ifHeaders')
    if 'ifQueries' in data and 'if_queries' not in data:
        data['if_queries'] = data.pop('ifQueries')
    if 'ruleId' in data and 'ruleID' not in data:
        data['ruleID'] = data.pop('ruleId')
    if 'rule_id' in data and 'ruleID' not in data:
        data['ruleID'] = data.pop('rule_id')
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
    allow_internet_access = _single_alias_value(
        opts, 'allow_internet_access', 'allowInternetAccess')
    if allow_internet_access is not None:
        body['allowInternetAccess'] = allow_internet_access
    envs = _single_alias_value(opts, 'envs', 'envVars')
    if envs is not None:
        body['envVars'] = envs
    if opts.get('lifecycle') is not None:
        lifecycle = opts.get('lifecycle') or {}
        body['lifecycle'] = lifecycle
        on_timeout = lifecycle.get('on_timeout') or lifecycle.get('onTimeout')
        if on_timeout == 'pause':
            body['autoPause'] = True
    if opts.get('injections') is not None:
        body['injections'] = [_normalize_injection(
            item) for item in opts.get('injections')]
    if opts.get('resources') is not None:
        body['resources'] = _normalize_resources(opts.get('resources'))
    return body


def _single_alias_value(opts, *names):
    present = [name for name in names if opts.get(name) is not None]
    if len(present) > 1:
        raise SandboxError(
            'Conflicting sandbox create options: {0}'.format(
                ', '.join(present)))
    if present:
        return opts.get(present[0])
    return None


def _require_sandbox_id(sandbox_id):
    if not sandbox_id:
        raise SandboxError('sandbox_id is required')
    return sandbox_id


def _normalize_list_options(opts):
    opts = dict(opts or {})
    query = opts.pop('query', None) or {}
    metadata = query.get('metadata')
    if metadata is not None:
        opts['metadata'] = metadata
    if isinstance(opts.get('metadata'), dict):
        opts['metadata'] = urlencode(opts.get('metadata'))
    for key, value in query.items():
        if (
                key not in ('metadata', 'state', 'template') and
                key not in opts and
                value is not None):
            opts[key] = value
    for key in ('state', 'template'):
        if query.get(key) is not None and opts.get(key) is None:
            opts[key] = query.get(key)
        value = opts.get(key)
        if isinstance(value, bytes_type):
            opts[key] = value.decode('utf-8')
        elif hasattr(value, '__iter__') and not isinstance(
                value, (basestring, dict)):
            opts[key] = text_type(',').join(
                item.decode('utf-8')
                if isinstance(item, bytes_type)
                else text_type(item)
                for item in value
            )
        elif value is not None and not isinstance(value, basestring):
            opts[key] = text_type(value)
    return opts


def _sandbox_api_key_from_env():
    return (
        os.getenv('QINIU_SANDBOX_API_KEY') or
        os.getenv('QINIU_API_KEY') or
        os.getenv('E2B_API_KEY')
    )


class SandboxClient(object):
    def __init__(self, endpoint=None, api_url=None, api_key=None,
                 access_token=None, mac=None, access_key=None,
                 secret_key=None, session=None, timeout=None, **opts):
        access_key = access_key or os.getenv('QINIU_SANDBOX_ACCESS_KEY')
        secret_key = secret_key or os.getenv('QINIU_SANDBOX_SECRET_KEY')
        if (access_key and not secret_key) or (secret_key and not access_key):
            raise SandboxError(
                'Both access_key and secret_key must be provided')
        self.endpoint = normalize_endpoint(endpoint or api_url)
        self.api_key = api_key or _sandbox_api_key_from_env()
        self.access_token = access_token or os.getenv(
            'QINIU_SANDBOX_ACCESS_TOKEN')
        self.mac = mac
        if self.mac is None and access_key and secret_key:
            self.mac = QiniuMacAuth(access_key, secret_key)
        self.session = session or requests.Session()
        self.timeout = timeout if timeout is not None else 30

    def _headers(self, auth_type=None):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        if auth_type == 'qiniu':
            return headers
        if auth_type == 'accessToken':
            if not self.access_token:
                raise SandboxError(
                    'access_token is required for this operation')
            headers['Authorization'] = 'Bearer {0}'.format(
                self.access_token)
            return headers
        if self.api_key:
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
        try:
            response = self.session.send(prepared, timeout=self.timeout)
        except requests.RequestException as err:
            raise SandboxError('Sandbox API request failed: {0}'.format(err))
        if response.status_code < 200 or response.status_code >= 300:
            response_data = None
            try:
                response_data = response.json()
            except ValueError:
                try:
                    response_data = response.text
                except Exception:
                    response_data = getattr(response, 'content', None)
            message = 'Sandbox API request failed with status {0}'.format(
                response.status_code
            )
            if isinstance(response_data, dict):
                err_msg = response_data.get(
                    'message') or response_data.get('error')
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get('message') or err_msg.get('error')
                if err_msg:
                    message += ': {0}'.format(err_msg)
            elif isinstance(response_data, basestring) and response_data:
                if len(response_data) > 200:
                    response_data = response_data[:200] + '...'
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
        _require_sandbox_id(sandbox_id)
        return self._request(
            'GET', '/sandboxes/{0}'.format(encode_path(sandbox_id)))

    getSandbox = get_sandbox
    get_info = get_sandbox
    getInfo = get_sandbox

    def delete_sandbox(self, sandbox_id):
        _require_sandbox_id(sandbox_id)
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
        _require_sandbox_id(sandbox_id)
        return self._request(
            'POST',
            '/sandboxes/{0}/pause'.format(encode_path(sandbox_id)),
            body={},
            empty=True,
        )

    pauseSandbox = pause_sandbox

    def resume_sandbox(self, sandbox_id, **opts):
        _require_sandbox_id(sandbox_id)
        return self._request(
            'POST',
            '/sandboxes/{0}/resume'.format(encode_path(sandbox_id)),
            body=opts,
        )

    resumeSandbox = resume_sandbox

    def connect_sandbox(self, sandbox_id, timeout=15):
        _require_sandbox_id(sandbox_id)
        return self._request(
            'POST',
            '/sandboxes/{0}/connect'.format(encode_path(sandbox_id)),
            body={'timeout': timeout},
        )

    connectSandbox = connect_sandbox
    connect = connect_sandbox

    def update_sandbox_timeout(self, sandbox_id, timeout=None, **opts):
        _require_sandbox_id(sandbox_id)
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
        _require_sandbox_id(sandbox_id)
        return self._request(
            'POST',
            '/sandboxes/{0}/refreshes'.format(encode_path(sandbox_id)),
            body=opts,
            empty=True,
        )

    refreshSandbox = refresh_sandbox

    def update_sandbox(self, sandbox_id, **opts):
        _require_sandbox_id(sandbox_id)
        return self._request(
            'PATCH',
            '/sandboxes/{0}'.format(encode_path(sandbox_id)),
            body=opts,
        )

    updateSandbox = update_sandbox

    def get_sandbox_injections(self, sandbox_id):
        _require_sandbox_id(sandbox_id)
        return self._request(
            'GET',
            '/sandboxes/{0}/injections'.format(encode_path(sandbox_id)),
        )

    getSandboxInjections = get_sandbox_injections

    def update_sandbox_injections(self, sandbox_id, injections):
        _require_sandbox_id(sandbox_id)
        if injections is None:
            raise SandboxError('injections is required')
        if isinstance(injections, dict) or hasattr(injections, 'to_dict'):
            injections = [injections]
        return self._request(
            'PUT',
            '/sandboxes/{0}/injections'.format(encode_path(sandbox_id)),
            body={
                'injections': [
                    _normalize_injection(item) for item in injections
                ],
            },
            empty=True,
        )

    updateSandboxInjections = update_sandbox_injections

    def update_sandbox_github_token(
            self, sandbox_id, authorization_token=None, **opts):
        _require_sandbox_id(sandbox_id)
        if authorization_token is None:
            authorization_token = (
                opts.get('authorizationToken') or opts.get('token'))
        if not authorization_token:
            raise SandboxError('authorization_token is required')
        return self._request(
            'PUT',
            '/sandboxes/{0}/github-token'.format(encode_path(sandbox_id)),
            body={'authorization_token': authorization_token},
            empty=True,
        )

    updateSandboxGithubToken = update_sandbox_github_token

    def get_sandbox_metrics(self, sandbox_id, **opts):
        _require_sandbox_id(sandbox_id)
        return self._request(
            'GET',
            '/sandboxes/{0}/metrics'.format(encode_path(sandbox_id)),
            params=opts,
        )

    getSandboxMetrics = get_sandbox_metrics
    get_metrics = get_sandbox_metrics
    getMetrics = get_sandbox_metrics

    def get_sandboxes_metrics(self, sandbox_ids):
        if not sandbox_ids:
            raise SandboxError('At least one sandbox ID must be provided')
        values = sandbox_ids
        if isinstance(sandbox_ids, dict):
            values = sandbox_ids.get(
                'sandbox_ids') or sandbox_ids.get('sandboxIDs')
            if values is None:
                values = [sandbox_ids]
        if values is None:
            raise SandboxError('At least one sandbox ID must be provided')
        if isinstance(values, (list, tuple, set)):
            values = list(values)
        elif hasattr(values, '__iter__') and not isinstance(
                values, (basestring, dict)):
            values = list(values)
        else:
            values = [values]
        ids = []
        for value in values:
            if isinstance(value, basestring):
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
        _require_sandbox_id(sandbox_id)
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
        if not template_id:
            raise SandboxError('template_id is required')
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
        start = _monotonic_time()
        while True:
            try:
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
            except SandboxError as err:
                if isinstance(err, TemplateBuildError) or (
                        err.status_code is not None and
                        err.status_code >= 400 and err.status_code < 500):
                    raise
            if _monotonic_time() - start >= timeout:
                raise SandboxError('Sandbox template build polling timed out')
            time.sleep(interval)

    waitForBuild = wait_for_build
