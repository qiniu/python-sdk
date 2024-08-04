from qiniu.http.region import Region, ServiceName
from qiniu.region import LegacyRegion
from qiniu.compat import json


class TestLegacyRegion:
    def test_compatible_with_http_region(self):
        mocked_hosts = {
            ServiceName.UP: ['https://up.python-example.qiniu.com', 'https://up-2.python-example.qiniu.com'],
            ServiceName.IO: ['https://io.python-example.qiniu.com'],
            ServiceName.RS: ['https://rs.python-example.qiniu.com'],
            ServiceName.RSF: ['https://rsf.python-example.qiniu.com'],
            ServiceName.API: ['https://api.python-example.qiniu.com']
        }

        region = LegacyRegion(
            up_host=mocked_hosts[ServiceName.UP][0],
            up_host_backup=mocked_hosts[ServiceName.UP][1],
            io_host=mocked_hosts[ServiceName.IO][0],
            rs_host=mocked_hosts[ServiceName.RS][0],
            rsf_host=mocked_hosts[ServiceName.RSF][0],
            api_host=mocked_hosts[ServiceName.API][0]
        )
        assert isinstance(region, Region)
        assert mocked_hosts == {
            k: [
                e.get_value()
                for e in region.services[k]
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
