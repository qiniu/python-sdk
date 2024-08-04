import pytest

from qiniu import Zone

TEST_RS_HOST = 'rs.test.region.compatible.config.qiniu.com'
TEST_RSF_HOST = 'rsf.test.region.compatible.config.qiniu.com'
TEST_API_HOST = 'api.test.region.compatible.config.qiniu.com'


class TestQiniuConfWithZone:
    """
    Test qiniu.conf with Zone(aka legacy Region)
    """

    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'default_rs_host': TEST_RS_HOST,
                'default_rsf_host': TEST_RSF_HOST,
                'default_api_host': TEST_API_HOST
            }
        ],
        indirect=True
    )
    def test_config_compatible(self, set_conf_default):
        zone = Zone()
        assert zone.get_rs_host("mock_ak", "mock_bucket") == TEST_RS_HOST
        assert zone.get_rsf_host("mock_ak", "mock_bucket") == TEST_RSF_HOST
        assert zone.get_api_host("mock_ak", "mock_bucket") == TEST_API_HOST

    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'default_query_region_host': 'https://fake-uc.phpsdk.qiniu.com'
            }
        ],
        indirect=True
    )
    def test_query_region_with_custom_domain(self, access_key, bucket_name, set_conf_default):
        with pytest.raises(Exception) as exc:
            zone = Zone()
            data = zone.bucket_hosts(access_key, bucket_name)
        assert data is None
        assert 'HTTP Status Code -1' in str(exc)

    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'default_query_region_host': 'https://fake-uc.phpsdk.qiniu.com',
                'default_query_region_backup_hosts': [
                    'unavailable-uc.phpsdk.qiniu.com',
                    'uc.qbox.me'
                ]
            }
        ],
        indirect=True
    )
    def test_query_region_with_backup_domains(self, access_key, bucket_name, set_conf_default):
        zone = Zone()
        data = zone.bucket_hosts(access_key, bucket_name)
        assert data != 'null'

    @pytest.mark.parametrize(
        'set_conf_default',
        [
            {
                'default_uc_host': 'https://fake-uc.phpsdk.qiniu.com',
                'default_query_region_backup_hosts': [
                    'unavailable-uc.phpsdk.qiniu.com',
                    'uc.qbox.me'
                ]
            }
        ],
        indirect=True
    )
    def test_query_region_with_uc_and_backup_domains(self, access_key, bucket_name, set_conf_default):
        zone = Zone()
        data = zone.bucket_hosts(access_key, bucket_name)
        assert data != 'null'
