from datetime import datetime, timedelta
from itertools import chain

from qiniu.http.endpoint import Endpoint
from qiniu.http.region import Region, ServiceName


class TestRegion:
    def test_default_options(self):
        region = Region('z0')
        assert region.region_id == 'z0'
        assert region.s3_region_id == 'z0'
        assert all(k in region.services for k in ServiceName)
        assert datetime.now() - region.create_time < timedelta(seconds=1)
        assert region.ttl == 86400
        assert region.is_live

    def test_custom_options(self):
        region = Region(
            region_id='z0',
            s3_region_id='s3-z0',
            services={
                ServiceName.UP: [
                    Endpoint('uc.python-sdk.qiniu.com')
                ],
                'custom-service': [
                    Endpoint('custom-service.python-sdk.qiniu.com')
                ]
            },
            create_time=datetime.now() - timedelta(days=1),
            ttl=3600
        )
        assert region.region_id == 'z0'
        assert region.s3_region_id == 's3-z0'
        assert all(
            k in region.services
            for k in chain(ServiceName, ['custom-service'])
        )
        assert datetime.now() - region.create_time > timedelta(days=1)
        assert region.ttl == 3600
        assert not region.is_live

    def test_from_region_id(self):
        region = Region.from_region_id('z0')

        expect_services_endpoint_value = {
            ServiceName.UC: [
                'https://uc.qiniuapi.com'
            ],
            ServiceName.UP: [
                'https://up.qiniup.com',
                'https://up.qbox.me'
            ],
            ServiceName.UP_ACC: [],
            ServiceName.IO: [
                'https://iovip.qiniuio.com',
                'https://iovip.qbox.me'
            ],
            ServiceName.RS: [
                'https://rs-z0.qiniuapi.com',
                'https://rs-z0.qbox.me'
            ],
            ServiceName.RSF: [
                'https://rsf-z0.qiniuapi.com',
                'https://rsf-z0.qbox.me'
            ],
            ServiceName.API: [
                'https://api-z0.qiniuapi.com',
                'https://api-z0.qbox.me'
            ],
            ServiceName.S3: [
                'https://s3.z0.qiniucs.com'
            ]
        }

        assert region.region_id == 'z0'
        assert region.s3_region_id == 'z0'

        assert {
            k: [
                e.get_value()
                for e in v
            ]
            for k, v in region.services.items()
        } == expect_services_endpoint_value

        assert datetime.now() - region.create_time < timedelta(seconds=1)
        assert region.ttl == 86400
        assert region.is_live

    def test_from_region_id_with_custom_options(self):
        preferred_scheme = 'http'
        custom_service_endpoint = Endpoint('custom-service.python-sdk.qiniu.com')
        region_z1 = Region.from_region_id(
            'z1',
            s3_region_id='s3-z1',
            ttl=-1,
            create_time=datetime.fromtimestamp(0),
            extended_services= {
                'custom-service': [
                    custom_service_endpoint
                ]
            },
            preferred_scheme=preferred_scheme
        )

        expect_services_endpoint_value = {
            ServiceName.UC: [
                preferred_scheme + '://uc.qiniuapi.com'
            ],
            ServiceName.UP: [
                preferred_scheme + '://up-z1.qiniup.com',
                preferred_scheme + '://up-z1.qbox.me'
            ],
            ServiceName.UP_ACC: [],
            ServiceName.IO: [
                preferred_scheme + '://iovip-z1.qiniuio.com',
                preferred_scheme + '://iovip-z1.qbox.me'
            ],
            ServiceName.RS: [
                preferred_scheme + '://rs-z1.qiniuapi.com',
                preferred_scheme + '://rs-z1.qbox.me'
            ],
            ServiceName.RSF: [
                preferred_scheme + '://rsf-z1.qiniuapi.com',
                preferred_scheme + '://rsf-z1.qbox.me'
            ],
            ServiceName.API: [
                preferred_scheme + '://api-z1.qiniuapi.com',
                preferred_scheme + '://api-z1.qbox.me'
            ],
            ServiceName.S3: [
                preferred_scheme + '://s3.z1.qiniucs.com'
            ],
            'custom-service': [
                custom_service_endpoint.get_value()
            ]
        }

        assert region_z1.region_id == 'z1'
        assert region_z1.s3_region_id == 's3-z1'
        assert {
            k: [
                e.get_value()
                for e in v
            ]
            for k, v in region_z1.services.items()
        } == expect_services_endpoint_value
        assert region_z1.ttl == -1
        assert region_z1.create_time == datetime.fromtimestamp(0)
        assert region_z1.is_live

    def test_clone(self):
        region = Region.from_region_id('z0')
        cloned_region = region.clone()
        cloned_region.region_id = 'another'
        cloned_region.services[ServiceName.UP][0].host = 'another-uc.qiniuapi.com'
        assert region.region_id == 'z0'
        assert region.services[ServiceName.UP][0].get_value() == 'https://up.qiniup.com'
        assert cloned_region.services[ServiceName.UP][0].get_value() == 'https://another-uc.qiniuapi.com'

    def test_merge(self):
        r1 = Region.from_region_id('z0')
        r2 = Region(
            region_id='r2',
            s3_region_id='s3-r2',
            services={
                ServiceName.UP: [
                    Endpoint('up-r2.python-sdk.qiniu.com')
                ],
                'custom-service': [
                    Endpoint('custom-service-r2.python-sdk.qiniu.com')
                ]
            },
            create_time=datetime.now() - timedelta(days=1),
            ttl=3600
        )

        merged_region = Region.merge(r1, r2)

        assert merged_region.region_id == r1.region_id
        assert merged_region.s3_region_id == r1.s3_region_id
        assert merged_region.create_time == r1.create_time
        assert merged_region.ttl == r1.ttl

        assert all(
            k in merged_region.services
            for k in [
                ServiceName.UP,
                'custom-service'
            ]
        ), merged_region.services.keys()

        for k, v in merged_region.services.items():
            if k == ServiceName.UP:
                assert v == list(chain(r1.services[k], r2.services[k]))
            elif k == 'custom-service':
                assert v == r2.services[k]
            else:
                assert v == r1.services[k]
