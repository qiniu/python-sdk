import os

import pytest

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
def qn_auth(access_key, secret_key):
    yield Auth(access_key, secret_key)


@pytest.fixture(scope='session')
def is_travis():
    """
    migrate from old test cases.
    seems useless.
    """
    yield os.getenv('QINIU_TEST_ENV') == 'travis'
