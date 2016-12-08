# -*- coding: utf-8 -*-
"""
=======================
    注意：必须手动运行
=======================
"""
import os
import sys
import time
import logging
import pytest
from qiniu import auth
from qiniu.services import compute


access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
qn_auth = auth.QiniuMacAuth(access_key, secret_key)
acc_client = compute.app.AccountClient(qn_auth)
qcos_client = None
user_name = ''
app_uri = ''
app_name = 'appjust4test'
app_region = 'nq'


def setup_module(module):
    acc_client = compute.app.AccountClient(qn_auth)
    user_info = acc_client.get_account_info()[0]
    acc_client.create_app({'name': app_name, 'title': 'whatever', 'region': app_region})

    module.user_name = user_info['name']
    module.app_uri = '{0}.{1}'.format(module.user_name, app_name)
    module.qcos_client = acc_client.create_qcos_client(module.app_uri)


def teardown_module(module):
    module.app_uri
    acc_client.delete_app(module.app_uri)


class TestApp:
    """应用测试用例"""

    def test_create_and_delete_app(self):
        _name_create = 'appjust4testcreate'
        _uri_create = ''
        _args = {'name': _name_create, 'title': 'whatever', 'region': app_region}

        with Call(acc_client, 'create_app', _args) as r:
            assert r[0] is not None
            _uri_create = r[0]['uri']

        with Call(acc_client, 'delete_app', _uri_create) as r:
            assert r[0] == {}

    def test_get_app_keys(self):
        with Call(acc_client, 'get_app_keys', app_uri) as r:
            assert len(r[0]) > 0

    def test_get_account_info(self):
        with Call(acc_client, 'get_account_info') as r:
            assert r[0] is not None


class TestStack:
    """服务组测试用例"""

    _name = 'just4test'
    _name_del = 'just4del'
    _name_create = 'just4create'

    @classmethod
    def setup_class(cls):
        qcos_client.create_stack({'name': cls._name})
        qcos_client.create_stack({'name': cls._name_del})

    @classmethod
    def teardown_class(cls):
        qcos_client.delete_stack(cls._name)
        qcos_client.delete_stack(cls._name_create)
        qcos_client.delete_stack(cls._name_del)

    def test_create_stack(self):
        with Call(qcos_client, 'create_stack', {'name': self._name_create}) as r:
            assert r[0] == {}

    def test_delete_stack(self):
        with Call(qcos_client, 'delete_stack', self._name_del) as r:
            assert r[0] == {}

    def test_list_stacks(self):
        with Call(qcos_client, 'list_stacks') as r:
            assert len(r) > 0
            assert self._name in [stack['name'] for stack in r[0]]

    def test_get_stack(self):
        with Call(qcos_client, 'get_stack', self._name) as r:
            assert r[0]['name'] == self._name

    def test_start_stack(self):
        with Call(qcos_client, 'start_stack', self._name) as r:
            assert r[0] == {}

    def test_stop_stack(self):
        with Call(qcos_client, 'stop_stack', self._name) as r:
            assert r[0] == {}


class TestService:
    """服务测试用例"""

    _stack = 'just4test2'
    _name = 'spaceship'
    _name_del = 'spaceship4del'
    _name_create = 'spaceship4create'
    _image = 'library/nginx:stable'
    _unit = '1U1G'
    _spec = {'image': _image, 'unitType': _unit}

    @classmethod
    def setup_class(cls):
        qcos_client.delete_stack(cls._stack)
        qcos_client.create_stack({'name': cls._stack})
        qcos_client.create_service(cls._stack, {'name': cls._name, 'spec': cls._spec})
        qcos_client.create_service(cls._stack, {'name': cls._name_del, 'spec': cls._spec})

        _debug_info('waiting for services to setup ...')
        time.sleep(10)

    @classmethod
    def teardown_class(cls):
        # 删除stack会清理所有相关服务
        qcos_client.delete_stack(cls._stack)

    def test_create_service(self):
        service = {'name': self._name_create, 'spec': self._spec}
        with Call(qcos_client, 'create_service', self._stack, service) as r:
            assert r[0] == {}

    def test_delete_service(self):
        with Call(qcos_client, 'delete_service', self._stack, self._name_del) as r:
            assert r[0] == {}

    def test_list_services(self):
        with Call(qcos_client, 'list_services', self._stack) as r:
            assert len(r) > 0
            assert self._name in [service['name'] for service in r[0]]

    def test_get_service_inspect(self):
        with Call(qcos_client, 'get_service_inspect', self._stack, self._name) as r:
            assert r[0]['name'] == self._name
            assert r[0]['spec']['unitType'] == self._unit

    def test_update_service(self):
        data = {'spec': {'autoRestart': 'ON_FAILURE'}}
        with Call(qcos_client, 'update_service', self._stack, self._name, data) as r:
            assert r[0] == {}

        _debug_info('waiting for update services to ready ...')
        time.sleep(10)

    def test_scale_service(self):
        data = {'instanceNum': 2}
        with Call(qcos_client, 'scale_service', self._stack, self._name, data) as r:
            assert r[0] == {}

        _debug_info('waiting for scale services to ready ...')
        time.sleep(10)


class TestContainer:
    """容器测试用例"""

    _stack = 'just4test3'
    _service = 'spaceship'
    _spec = {'image': 'library/nginx:stable', 'unitType': '1U1G'}
    # 为了方便测试，容器数量最少为2
    _instanceNum = 2

    @classmethod
    def setup_class(cls):
        qcos_client.delete_stack(cls._stack)
        qcos_client.create_stack({'name': cls._stack})
        qcos_client.create_service(cls._stack, {'name': cls._service, 'spec': cls._spec, 'instanceNum': cls._instanceNum})

        _debug_info('waiting for containers to setup ...')
        time.sleep(10)

    @classmethod
    def teardown_class(cls):
        qcos_client.delete_stack(cls._stack)

    def test_list_containers(self):
        with Call(qcos_client, 'list_containers', self._stack, self._service) as r:
            assert len(r[0]) > 0
            assert len(r[0]) <= self._instanceNum

    def test_get_container_inspect(self):
        ips = qcos_client.list_containers(self._stack, self._service)[0]
        # 查看第1个容器
        with Call(qcos_client, 'get_container_inspect', ips[0]) as r:
            assert r[0]['ip'] == ips[0]

    def test_stop_and_strat_container(self):
        ips = qcos_client.list_containers(self._stack, self._service)[0]
        # 停止第2个容器
        with Call(qcos_client, 'stop_container', ips[1]) as r:
            assert r[0] == {}

        _debug_info('waiting for containers to stop ...')
        time.sleep(3)

        # 启动第2个容器
        with Call(qcos_client, 'start_container', ips[1]) as r:
            assert r[0] == {}

    def test_restart_container(self):
        ips = qcos_client.list_containers(self._stack, self._service)[0]
        # 重启第1个容器
        with Call(qcos_client, 'restart_container', ips[0]) as r:
            assert r[0] == {}


class TestAp:
    """接入点测试用例"""

    _stack = 'just4test4'
    _service = 'spaceship'
    _spec = {'image': 'library/nginx:stable', 'unitType': '1U1G'}
    # 为了方便测试，容器数量最少为2
    _instanceNum = 2
    _apid_domain = {}
    _apid_ip = {}
    _apid_ip_port = 8080
    _user_domain = 'just4test001.example.com'

    @classmethod
    def setup_class(cls):
        qcos_client.delete_stack(cls._stack)
        qcos_client.create_stack({'name': cls._stack})
        qcos_client.create_service(cls._stack, {'name': cls._service, 'spec': cls._spec, 'instanceNum': cls._instanceNum})
        cls._ap_domain = qcos_client.create_ap({'type': 'DOMAIN', 'provider': 'Telecom', 'unitType': 'BW_10M', 'title': 'public1'})[0]
        cls._ap_ip = qcos_client.create_ap({'type': 'PUBLIC_IP', 'provider': 'Telecom', 'unitType': 'BW_10M', 'title': 'public2'})[0]
        qcos_client.set_ap_port(cls._ap_ip['apid'], cls._apid_ip_port, {'proto': 'http'})

    @classmethod
    def teardown_class(cls):
        qcos_client.delete_stack(cls._stack)
        qcos_client.delete_ap(cls._ap_domain['apid'])
        qcos_client.delete_ap(cls._ap_ip['apid'])

    def test_list_aps(self):
        with Call(qcos_client, 'list_aps') as r:
            assert len(r[0]) > 0
            assert self._ap_domain['apid'] in [ap['apid'] for ap in r[0]]
            assert self._ap_domain['apid'] in [ap['apid'] for ap in r[0]]

    def test_create_and_delete_ap(self):
        apid = 0
        ap = {'type': 'DOMAIN', 'provider': 'Telecom', 'unitType': 'BW_10M', 'title': 'public1'}

        with Call(qcos_client, 'create_ap', ap) as r:
            assert r[0] is not None and r[0]['apid'] > 0
            apid = r[0]['apid']

        with Call(qcos_client, 'delete_ap', apid) as r:
            assert r[0] == {}

    def test_search_ap(self):
        with Call(qcos_client, 'search_ap', 'ip', self._ap_ip['ip']) as r:
            assert str(r[0]['apid']) == self._ap_ip['apid']

    def test_get_ap(self):
        with Call(qcos_client, 'get_ap', self._ap_ip['apid']) as r:
            assert str(r[0]['apid']) == self._ap_ip['apid']

    def test_update_ap(self):
        with Call(qcos_client, 'update_ap', self._ap_ip['apid'], {}) as r:
            assert r[0] == {}

    def test_set_ap_port(self):
        with Call(qcos_client, 'set_ap_port', self._ap_ip['apid'], 80, {'proto': 'http'}) as r:
            assert r[0] == {}

    def test_publish_ap(self):
        domain = {'userDomain': self._user_domain}
        with Call(qcos_client, 'publish_ap', self._ap_domain['apid'], domain) as r:
            assert r[0] == {}

    def test_unpublish_ap(self):
        domain = {'userDomain': self._user_domain}
        with Call(qcos_client, 'unpublish_ap', self._ap_domain['apid'], domain) as r:
            assert r[0] == {}

    def test_get_ap_port_healthcheck(self):
        with Call(qcos_client, 'get_ap_port_healthcheck', self._ap_ip['apid'], self._apid_ip_port) as r:
            assert r[0] is not None

    def test_disable_ap_port(self):
        with Call(qcos_client, 'disable_ap_port', self._ap_ip['apid'], self._apid_ip_port) as r:
            assert r[0] == {}

    def test_enable_ap_port(self):
        with Call(qcos_client, 'enable_ap_port', self._ap_ip['apid'], self._apid_ip_port) as r:
            assert r[0] == {}

    def test_get_ap_providers(self):
        with Call(qcos_client, 'get_ap_providers') as r:
            assert len(r[0]) > 0


class Call(object):
    def __init__(self, obj, method, *args):
        self.context = (obj, method, args)
        self.result = None

    def __enter__(self):
        self.result = getattr(self.context[0], self.context[1])(*self.context[2])
        assert self.result is not None
        return self.result

    def __exit__(self, type, value, traceback):
        _debug_info('\033[94m%s.%s\x1b[0m: %s', self.context[0].__class__, self.context[1], self.result)


def _debug_info(*args):
    logger = logging.getLogger(__name__)
    logger.debug(*args)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    pytest.main()
