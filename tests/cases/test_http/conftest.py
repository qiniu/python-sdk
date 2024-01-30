import os

import pytest

from qiniu.compat import urlparse


@pytest.fixture(scope='session')
def mock_server_addr():
    addr = os.getenv('MOCK_SERVER_ADDRESS', 'http://localhost:9000')
    yield urlparse(addr)
