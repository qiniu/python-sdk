import pytest

from qiniu.http.endpoint import Endpoint
from qiniu.http.region import Region, ServiceName
from qiniu.http.regions_retry_policy import RegionsRetryPolicy
from qiniu.retry import Attempt


@pytest.fixture(scope='function')
def mocked_regions_provider():
    yield [
        Region.from_region_id('z0'),
        Region.from_region_id('z1')
    ]


class TestRegionsRetryPolicy:
    def test_init(self, mocked_regions_provider):
        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=mocked_regions_provider,
            service_names=[ServiceName.UP]
        )

        mocked_context = {}
        regions_retry_policy.init_context(mocked_context)

        assert mocked_context['region'] == mocked_regions_provider[0]
        assert mocked_context['alternative_regions'] == mocked_regions_provider[1:]
        assert mocked_context['service_name'] == ServiceName.UP
        assert mocked_context['alternative_service_names'] == []
        assert mocked_context['endpoint'] == mocked_regions_provider[0].services[ServiceName.UP][0]
        assert mocked_context['alternative_endpoints'] == mocked_regions_provider[0].services[ServiceName.UP][1:]

    @pytest.mark.parametrize(
        'regions,service_names,expect_should_retry,msg',
        [
            (
                [
                    Region.from_region_id('z0'),
                    Region.from_region_id('z1')
                ],
                [ServiceName.UP],
                True,
                'Should retry when there are alternative regions'
            ),
            (
                [
                    Region.from_region_id(
                        'z0',
                        extended_services={
                            ServiceName.UP_ACC: [
                                Endpoint('python-sdk.kodo-accelerate.cn-east-1.qiniucs.com')
                            ]
                        }
                    )
                ],
                [ServiceName.UP_ACC, ServiceName.UP],
                True,
                'Should retry when there are alternative services'
            ),
            (
                [
                    Region.from_region_id('z0')
                ],
                [ServiceName.UP_ACC, ServiceName.UP],
                False,
                'Should not retry when there are no alternative regions or empty endpoint in services'
            ),
            (
                [
                    Region.from_region_id('z0')
                ],
                [ServiceName.UP],
                False,
                'Should not retry when there are no alternative regions or services'
            ),
        ],
        ids=lambda v: v if type(v) is str else ''
    )
    def test_should_retry(
        self,
        regions,
        service_names,
        expect_should_retry,
        msg
    ):
        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=regions,
            service_names=service_names
        )

        mocked_attempt = Attempt()
        regions_retry_policy.init_context(mocked_attempt.context)

        assert regions_retry_policy.should_retry(mocked_attempt) == expect_should_retry, msg

    @pytest.mark.parametrize(
        'regions,service_names',
        [
            (
                [
                    Region.from_region_id('z0'),
                    Region.from_region_id('z1')
                ],
                [ServiceName.UP]
            ),
            (
                [
                    Region.from_region_id(
                        'z0',
                        extended_services={
                            ServiceName.UP_ACC: [
                                Endpoint('python-sdk.kodo-accelerate.cn-east-1.qiniucs.com')
                            ]
                        }
                    )
                ],
                [ServiceName.UP_ACC, ServiceName.UP]
            )
        ]
    )
    def test_prepare_retry(self, regions, service_names):
        mocked_attempt = Attempt()

        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=regions,
            service_names=service_names
        )
        regions_retry_policy.init_context(mocked_attempt.context)

        actual_tried_endpoints = [
            mocked_attempt.context.get('endpoint')
        ]
        while regions_retry_policy.should_retry(mocked_attempt):
            regions_retry_policy.prepare_retry(mocked_attempt)
            actual_tried_endpoints.append(mocked_attempt.context.get('endpoint'))

        # There is no endpoints retry policy,
        # so just the first endpoint will be tried
        expect_tried_endpoints = [
            r.services[sn][0]
            for r in regions
            for sn in service_names
            if sn in r.services and r.services[sn]
        ]

        print(actual_tried_endpoints)
        print(expect_tried_endpoints)

        assert [
            e.get_value()
            for e in actual_tried_endpoints
        ] == [
            e.get_value()
            for e in expect_tried_endpoints
        ]

    @pytest.mark.parametrize(
        'regions,service_names,expect_change_region_times',
        [
            # tow region, retry once
            (
                [
                    Region.from_region_id('z0'),
                    Region.from_region_id('z1')
                ],
                [ServiceName.UP],
                1
            ),
            # one region, tow service, retry service once, region zero
            (
                [
                    Region.from_region_id(
                        'z0',
                        extended_services={
                            ServiceName.UP_ACC: [
                                Endpoint('python-sdk.kodo-accelerate.cn-east-1.qiniucs.com')
                            ]
                        }
                    )
                ],
                [ServiceName.UP_ACC, ServiceName.UP],
                0
            ),
            # tow region, tow service, retry service once, region once
            (
                [
                    Region.from_region_id(
                        'z0',
                        extended_services={
                            ServiceName.UP_ACC: [
                                Endpoint('python-sdk.kodo-accelerate.cn-east-1.qiniucs.com')
                            ]
                        }
                    ),
                    Region.from_region_id('z1')
                ],
                [ServiceName.UP_ACC, ServiceName.UP],
                1
            )
        ]
    )
    def test_on_change_region_option(
        self,
        regions,
        service_names,
        expect_change_region_times,
        use_ref
    ):
        actual_change_region_times_ref = use_ref(0)

        def handle_change_region(_context):
            actual_change_region_times_ref.value += 1

        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=regions,
            service_names=service_names,
            on_change_region=handle_change_region
        )

        mocked_attempt = Attempt()
        regions_retry_policy.init_context(mocked_attempt.context)

        while regions_retry_policy.should_retry(mocked_attempt):
            regions_retry_policy.prepare_retry(mocked_attempt)

        assert actual_change_region_times_ref.value == expect_change_region_times

    def test_init_with_preferred_endpoints_option_new_temp_region(self, mocked_regions_provider):
        preferred_endpoints = [
            Endpoint('python-sdk.kodo-accelerate.cn-east-1.qiniucs.com')
        ]
        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=mocked_regions_provider,
            service_names=[ServiceName.UP],
            preferred_endpoints_provider=preferred_endpoints
        )

        mocked_context = {}
        regions_retry_policy.init_context(mocked_context)

        assert mocked_context['region'].region_id == 'preferred_region'
        assert mocked_context['region'].services[ServiceName.UP] == preferred_endpoints
        assert mocked_context['alternative_regions'] == list(mocked_regions_provider)

    def test_init_with_preferred_endpoints_option_reorder_regions(self, mocked_regions_provider):
        mocked_regions = list(mocked_regions_provider)
        preferred_region_index = 1
        preferred_endpoints = [
            mocked_regions[preferred_region_index].services[ServiceName.UP][0]
        ]
        regions_retry_policy = RegionsRetryPolicy(
            regions_provider=mocked_regions_provider,
            service_names=[ServiceName.UP],
            preferred_endpoints_provider=preferred_endpoints
        )

        mocked_context = {}
        regions_retry_policy.init_context(mocked_context)

        assert mocked_context['region'] == mocked_regions[preferred_region_index]
        mocked_regions.pop(preferred_region_index)
        assert mocked_context['alternative_regions'] == mocked_regions
