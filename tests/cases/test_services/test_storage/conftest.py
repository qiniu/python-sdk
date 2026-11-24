import os
from collections import namedtuple
from hashlib import new as hashlib_new
import tempfile

import pytest

import requests

from qiniu import BucketManager
from qiniu.utils import io_md5
from qiniu.config import QUERY_REGION_HOST, QUERY_REGION_BACKUP_HOSTS
from qiniu.http.endpoint import Endpoint
from qiniu.http.regions_provider import Region, ServiceName, get_default_regions_provider


@pytest.fixture(scope='session')
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


@pytest.fixture(scope='session')
def get_real_regions():
    def _get_real_regions(access_key, bucket_name):
        regions = list(
            get_default_regions_provider(
                query_endpoints_provider=[
                    Endpoint.from_host(h)
                    for h in [QUERY_REGION_HOST] + QUERY_REGION_BACKUP_HOSTS
                ],
                access_key=access_key,
                bucket_name=bucket_name
            )
        )

        if not regions:
            raise RuntimeError('No regions found')

        return regions

    yield _get_real_regions


@pytest.fixture(scope='function')
def regions_with_real_endpoints(access_key, bucket_name, get_real_regions):
    yield get_real_regions(access_key, bucket_name)


@pytest.fixture(scope='function')
def regions_with_fake_endpoints(regions_with_real_endpoints):
    """
    Returns
    -------
    list[Region]
        The first element is the fake region with fake endpoints for every service.
        The second element is the real region with first fake endpoint for every service.
        The rest elements are real regions with real endpoints if exists.
    """
    regions = regions_with_real_endpoints

    regions[0].services = {
        sn: [
            Endpoint('fake-{0}.python-sdk.qiniu.com'.format(sn.value))
        ] + endpoints
        for sn, endpoints in regions[0].services.items()
    }

    regions.insert(0, Region(
        'fake-id',
        'fake-s3-id',
        services={
            sn: [
                Endpoint('fake-region-{0}.python-sdk.qiniu.com'.format(sn.value))
            ]
            for sn in ServiceName
        }
    ))

    yield regions


TempFile = namedtuple(
    'TempFile',
    [
        'path',
        'md5',
        'name',
        'size'
    ]
)


@pytest.fixture(scope='function')
def temp_file(request):
    size = 4 * 1024
    if hasattr(request, 'param'):
        size = request.param

    tmp_file_path = tempfile.mktemp()
    chunk_size = 4 * 1024

    md5_hasher = hashlib_new('md5')
    with open(tmp_file_path, 'wb') as f:
        remaining_bytes = size
        while remaining_bytes > 0:
            chunk = os.urandom(min(chunk_size, remaining_bytes))
            f.write(chunk)
            md5_hasher.update(chunk)
            remaining_bytes -= len(chunk)

    yield TempFile(
        path=tmp_file_path,
        md5=md5_hasher.hexdigest(),
        name=os.path.basename(tmp_file_path),
        size=size
    )

    try:
        os.remove(tmp_file_path)
    except Exception:
        pass
