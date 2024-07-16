import pytest

import requests

from qiniu import BucketManager
from qiniu.utils import io_md5


@pytest.fixture()
def bucket_manager(qn_auth):
    yield BucketManager(qn_auth)


@pytest.fixture(scope='session')
def get_remote_object_headers_and_md5(download_domain):
    def fetch_calc_md5(key=None, scheme=None, url=None):
        if not key and not url:
            raise TypeError('Must provide key or url')

        scheme = scheme if scheme is not None else 'http'
        download_url = '{}://{}/{}'.format(scheme, download_domain, key)
        if url:
            download_url = url

        resp = requests.get(download_url, stream=True)
        resp.raise_for_status()

        return resp.headers, io_md5(resp.iter_content(chunk_size=8192))

    yield fetch_calc_md5
