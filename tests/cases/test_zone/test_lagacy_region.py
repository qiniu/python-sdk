import pytest

from qiniu.http.region import Region, ServiceName
from qiniu.region import LegacyRegion
from qiniu.compat import json, is_py2


@pytest.fixture
def mocked_hosts():
    mocked_hosts = {
        ServiceName.UP: ['https://up.python-example.qiniu.com', 'https://up-2.python-example.qiniu.com'],
        ServiceName.IO: ['https://io.python-example.qiniu.com'],
        ServiceName.RS: ['https://rs.python-example.qiniu.com'],
        ServiceName.RSF: ['https://rsf.python-example.qiniu.com'],
        ServiceName.API: ['https://api.python-example.qiniu.com']
    }
    yield mocked_hosts


@pytest.fixture
def mock_legacy_region(mocked_hosts):
    region = LegacyRegion(
        up_host=mocked_hosts[ServiceName.UP][0],
        up_host_backup=mocked_hosts[ServiceName.UP][1],
        io_host=mocked_hosts[ServiceName.IO][0],
        rs_host=mocked_hosts[ServiceName.RS][0],
        rsf_host=mocked_hosts[ServiceName.RSF][0],
        api_host=mocked_hosts[ServiceName.API][0]
    )
    yield region


class TestLegacyRegion:
    def test_get_hosts_from_self(self, mocked_hosts, mock_legacy_region, qn_auth, bucket_name):
        cases = [
            # up will always query from the old version,
            # which version implements the `get_up_host_*` method
            (
                mock_legacy_region.get_io_host(qn_auth.get_access_key(), None),
                mocked_hosts[ServiceName.IO][0]
            ),
            (
                mock_legacy_region.get_rs_host(qn_auth.get_access_key(), None),
                mocked_hosts[ServiceName.RS][0]
            ),
            (
                mock_legacy_region.get_rsf_host(qn_auth.get_access_key(), None),
                mocked_hosts[ServiceName.RSF][0]
            ),
            (
                mock_legacy_region.get_api_host(qn_auth.get_access_key(), None),
                mocked_hosts[ServiceName.API][0]
            )
        ]
        for actual, expect in cases:
            assert actual == expect

    def test_get_hosts_from_query(self, qn_auth, bucket_name):
        up_token = qn_auth.upload_token(bucket_name)
        region = LegacyRegion()
        up_host = region.get_up_host_by_token(up_token, None)
        up_host_backup = region.get_up_host_backup_by_token(up_token, None)
        if is_py2:
            up_host = up_host.encode()
            up_host_backup = up_host_backup.encode()
        assert type(up_host) is str and len(up_host) > 0
        assert type(up_host_backup) is str and len(up_host_backup) > 0
        assert up_host != up_host_backup

    def test_compatible_with_http_region(self, mocked_hosts, mock_legacy_region):
        assert isinstance(mock_legacy_region, Region)
        assert mocked_hosts == {
            k: [
                e.get_value()
                for e in mock_legacy_region.services[k]
            ]
            for k in mocked_hosts
        }

    def test_get_bucket_hosts(self, access_key, bucket_name):
        region = LegacyRegion()
        bucket_hosts = region.get_bucket_hosts(access_key, bucket_name)
        for k in [
            'upHosts',
            'ioHosts',
            'rsHosts',
            'rsfHosts',
            'apiHosts'
        ]:
            assert all(h.startswith('http') for h in bucket_hosts[k]), bucket_hosts[k]

    def test_bucket_hosts(self, access_key, bucket_name):
        region = LegacyRegion()
        bucket_hosts_str = region.bucket_hosts(access_key, bucket_name)
        bucket_hosts = json.loads(bucket_hosts_str)

        region_hosts = bucket_hosts.get('hosts', [])

        assert len(region_hosts) > 0

        for r in region_hosts:
            for k in [
                'up',
                'io',
                'rs',
                'rsf',
                'api'
            ]:
                service_hosts = r[k].get('domains')
                assert len(service_hosts) > 0
                assert all(len(h) for h in service_hosts)
