import os
import datetime
import tempfile
import time
import json
from multiprocessing.pool import ThreadPool

import pytest

from qiniu.compat import urlparse
from qiniu.config import QUERY_REGION_HOST, QUERY_REGION_BACKUP_HOSTS
from qiniu.http.endpoint import Endpoint
from qiniu.http.region import Region
from qiniu.http.regions_provider import (
    CachedRegionsProvider,
    FileAlreadyLocked,
    QueryRegionsProvider,
    _FileThreadingLocker,
    _FileLocker,
    _global_cache_scope,
    _persist_region,
)


@pytest.fixture(scope='session')
def query_regions_endpoints_provider():
    query_region_host = urlparse(QUERY_REGION_HOST).hostname
    endpoints_provider = [
        Endpoint(h)
        for h in [query_region_host] + QUERY_REGION_BACKUP_HOSTS
    ]
    yield endpoints_provider


@pytest.fixture(scope='function')
def query_regions_provider(access_key, bucket_name, query_regions_endpoints_provider):
    query_regions_provider = QueryRegionsProvider(
        access_key=access_key,
        bucket_name=bucket_name,
        endpoints_provider=query_regions_endpoints_provider
    )
    yield query_regions_provider


@pytest.fixture(scope='function')
def temp_file_path(rand_string):
    p = os.path.join(tempfile.gettempdir(), rand_string(16))
    yield p
    try:
        os.remove(p)
    except FileNotFoundError:
        pass


class TestQueryRegionsProvider:
    def test_getter(self, query_regions_provider):
        ret = list(query_regions_provider)
        assert len(ret) > 0

    def test_error_with_bad_ak(self, query_regions_endpoints_provider):
        query_regions_provider = QueryRegionsProvider(
            access_key='fake',
            bucket_name='fake',
            endpoints_provider=query_regions_endpoints_provider
        )
        with pytest.raises(Exception) as exc:
            list(query_regions_provider)
        assert '612' in str(exc)

    def test_error_with_bad_endpoint(self, query_regions_provider):
        query_regions_provider.endpoints_provider = [
            Endpoint('fake-uc.python.qiniu.com')
        ]
        with pytest.raises(Exception) as exc:
            list(query_regions_provider)
        assert '-1' in str(exc)

    def test_getter_with_retried(self, query_regions_provider, query_regions_endpoints_provider):
        query_regions_provider.endpoints_provider = [
            Endpoint('fake-uc.python.qiniu.com'),
        ] + list(query_regions_endpoints_provider)

        ret = list(query_regions_provider)
        assert len(ret) > 0

    def test_getter_with_preferred_scheme(self, query_regions_provider):
        query_regions_provider.preferred_scheme = 'http'
        for region in query_regions_provider:
            for endpoints in region.services.values():
                assert all(
                    e.get_value().startswith('http://')
                    for e in endpoints
                )


@pytest.fixture(scope='function')
def cached_regions_provider(request):
    if not hasattr(request, 'param') or not isinstance(request.param, dict):
        request.param = {}
    request.param.setdefault('cache_key', 'test-cache-key')
    request.param.setdefault('base_regions_provider', [])

    cached_regions_provider = CachedRegionsProvider(
        **request.param
    )
    yield cached_regions_provider

    # clear memo_cache for test cases will affect each other with same cache_key
    _global_cache_scope.memo_cache.clear()
    persist_path = request.param.get('persist_path')
    if persist_path:
        try:
            os.remove(persist_path)
        except OSError:
            pass


@pytest.fixture(scope='function')
def bad_regions_provider():
    regions_provider = QueryRegionsProvider(
        access_key='fake',
        bucket_name='fake',
        endpoints_provider=[
            Endpoint('fake-uc.python.qiniu.com')
        ]
    )
    yield regions_provider


class TestCachedQueryRegionsProvider:
    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {'base_regions_provider': [Region.from_region_id('z0')]},
        ],
        indirect=True
    )
    def test_getter_normally(self, cached_regions_provider):
        ret = list(cached_regions_provider)
        assert len(ret) > 0

    def test_setter(self, cached_regions_provider):
        regions = [Region.from_region_id('z0')]
        cached_regions_provider.set_regions(regions)
        assert list(cached_regions_provider) == regions

    def test_getter_with_expired_file_cache(self, cached_regions_provider):
        expired_region = Region.from_region_id('z0')
        expired_region.create_time = datetime.datetime.now()

        r_z0 = Region.from_region_id('z0')
        r_z0.ttl = 86400

        with open(cached_regions_provider.persist_path, 'w') as f:
            json.dump({
                'cacheKey': cached_regions_provider.cache_key,
                'regions': [_persist_region(r) for r in [expired_region]]
            }, f)

        cached_regions_provider._cache_scope.memo_cache[cached_regions_provider.cache_key] = [r_z0]

        assert list(cached_regions_provider) == [r_z0]
        try:
            os.remove(cached_regions_provider.persist_path)
        except OSError:
            pass

    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {
                'persist_path': os.path.join(tempfile.gettempdir(), 'test-disable-persist.jsonl'),
            },
            {
                'persist_path': None,
            }
        ],
        indirect=True
    )
    def test_disable_persist(self, cached_regions_provider):
        if cached_regions_provider.persist_path:
            old_persist_path = cached_regions_provider.persist_path
            cached_regions_provider.persist_path = None
        else:
            old_persist_path = _global_cache_scope.persist_path

        regions = [Region.from_region_id('z0')]
        cached_regions_provider.set_regions(regions)

        assert list(cached_regions_provider) == regions
        assert not os.path.exists(old_persist_path)

    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {
                'persist_path': os.path.join(tempfile.gettempdir(), 'test-base-provider.jsonl'),
                'base_regions_provider': [Region.from_region_id('z0')]
            }
        ],
        indirect=True
    )
    def test_getter_with_base_regions_provider(self, cached_regions_provider):
        assert not os.path.exists(cached_regions_provider.persist_path)
        regions = list(cached_regions_provider.base_regions_provider)
        assert list(cached_regions_provider) == regions
        line_num = 0
        with open(cached_regions_provider.persist_path, 'r') as f:
            for l in f:
                # ignore empty line
                if l.strip():
                    line_num += 1
        assert line_num == 1

    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {
                'persist_path': os.path.join(tempfile.gettempdir(), 'test-base-provider.jsonl')
            }
        ],
        indirect=True
    )
    def test_should_provide_memo_expired_regions_when_base_provider_failed(
        self,
        cached_regions_provider,
        bad_regions_provider
    ):
        expired_region = Region.from_region_id('z0')
        expired_region.create_time = datetime.datetime.fromtimestamp(0)
        expired_region.ttl = 1
        cached_regions_provider.set_regions([expired_region])
        cached_regions_provider.base_regions_provider = bad_regions_provider
        regions = list(cached_regions_provider)
        assert len(regions) > 0
        assert not regions[0].is_live

    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {
                'persist_path': os.path.join(tempfile.gettempdir(), 'test-base-provider.jsonl')
            }
        ],
        indirect=True
    )
    def test_should_provide_file_expired_regions_when_base_provider_failed(
        self,
        cached_regions_provider,
        bad_regions_provider
    ):
        expired_region = Region.from_region_id('z0')
        expired_region.create_time = datetime.datetime.fromtimestamp(0)
        expired_region.ttl = 1
        cached_regions_provider.set_regions([expired_region])
        cached_regions_provider._cache_scope.memo_cache.clear()
        cached_regions_provider.base_regions_provider = bad_regions_provider
        regions = list(cached_regions_provider)
        assert len(regions) > 0
        assert not regions[0].is_live

    @pytest.mark.parametrize(
        'cached_regions_provider',
        [
            {
                'should_shrink_expired_regions': True
            }
        ],
        indirect=True
    )
    def test_shrink_with_expired_regions(self, cached_regions_provider):
        expired_region = Region.from_region_id('z0')
        expired_region.create_time = datetime.datetime.fromtimestamp(0)
        expired_region.ttl = 1
        origin_cache_key = cached_regions_provider.cache_key
        cached_regions_provider.set_regions([expired_region])
        cached_regions_provider.cache_key = 'another-cache-key'
        list(cached_regions_provider)  # trigger __shrink_cache()
        assert len(cached_regions_provider._cache_scope.memo_cache[origin_cache_key]) == 0

    def test_shrink_with_ignore_expired_regions(self, cached_regions_provider):
        expired_region = Region.from_region_id('z0')
        expired_region.create_time = datetime.datetime.fromtimestamp(0)
        expired_region.ttl = 1
        origin_cache_key = cached_regions_provider.cache_key
        cached_regions_provider.set_regions([expired_region])
        cached_regions_provider.cache_key = 'another-cache-key'
        list(cached_regions_provider)  # trigger __shrink_cache()
        assert len(cached_regions_provider._cache_scope.memo_cache[origin_cache_key]) > 0

    def test_file_locker(self, temp_file_path):
        handled_cnt = 0
        skipped_cnt = 0


        def process_file(_n):
            nonlocal handled_cnt, skipped_cnt
            try:
                with open(temp_file_path, 'w') as f, _FileThreadingLocker(f), _FileLocker(f):
                    time.sleep(1)
                    handled_cnt += 1
            except FileAlreadyLocked:
                skipped_cnt += 1


        ThreadPool(4).map(process_file, range(20))
        assert handled_cnt + skipped_cnt == 20
        assert 0 < handled_cnt <= 4
