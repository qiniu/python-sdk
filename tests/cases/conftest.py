# -*- coding: utf-8 -*-
import os
import random
import string

import pytest

from qiniu import config as qn_config
from qiniu import Auth


@pytest.fixture(scope='session')
def access_key():
    yield os.getenv('QINIU_ACCESS_KEY')


@pytest.fixture(scope='session')
def secret_key():
    yield os.getenv('QINIU_SECRET_KEY')


@pytest.fixture(scope='session')
def bucket_name():
    yield os.getenv('QINIU_TEST_BUCKET')


@pytest.fixture(scope='session')
def no_acc_bucket_name():
    yield os.getenv('QINIU_TEST_NO_ACC_BUCKET')


@pytest.fixture(scope='session')
def download_domain():
    yield os.getenv('QINIU_TEST_DOMAIN')


@pytest.fixture(scope='session')
def upload_callback_url():
    yield os.getenv('QINIU_UPLOAD_CALLBACK_URL')


@pytest.fixture(scope='session')
def qn_auth(access_key, secret_key):
    yield Auth(access_key, secret_key)


@pytest.fixture(scope='session')
def is_travis():
    """
    migrate from old test cases.
    seems useless.
    """
    yield os.getenv('QINIU_TEST_ENV') == 'travis'


@pytest.fixture(scope='function')
def set_conf_default(request):
    if hasattr(request, 'param'):
        qn_config.set_default(**request.param)
    yield
    qn_config._config = {
        'default_zone': None,
        'default_rs_host': qn_config.RS_HOST,
        'default_rsf_host': qn_config.RSF_HOST,
        'default_api_host': qn_config.API_HOST,
        'default_uc_host': qn_config.UC_HOST,
        'default_query_region_host': qn_config.QUERY_REGION_HOST,
        'default_query_region_backup_hosts': [
            'uc.qbox.me',
            'api.qiniu.com'
        ],
        'default_backup_hosts_retry_times': 2,
        'connection_timeout': 30,  # 链接超时为时间为30s
        'connection_retries': 3,  # 链接重试次数为3次
        'connection_pool': 10,  # 链接池个数为10
        'default_upload_threshold': 2 * qn_config._BLOCK_SIZE  # put_file上传方式的临界默认值
    }

    _is_customized_default = {
        'default_zone': False,
        'default_rs_host': False,
        'default_rsf_host': False,
        'default_api_host': False,
        'default_uc_host': False,
        'default_query_region_host': False,
        'default_query_region_backup_hosts': False,
        'default_backup_hosts_retry_times': False,
        'connection_timeout': False,
        'connection_retries': False,
        'connection_pool': False,
        'default_upload_threshold': False
    }


@pytest.fixture(scope='session')
def rand_string():
    def _rand_string(length):
        # use random.choices when min version of python >= 3.6
        return ''.join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(length)
        )
    yield _rand_string


class Ref:
    """
    python2 not support nonlocal keyword
    """
    def __init__(self, value=None):
        self.value = value


@pytest.fixture(scope='session')
def use_ref():
    def _use_ref(value):
        return Ref(value)

    yield _use_ref
