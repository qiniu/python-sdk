import pytest

from qiniu.http.endpoint import Endpoint
from qiniu.http.endpoints_retry_policy import EndpointsRetryPolicy
from qiniu.retry.attempt import Attempt


@pytest.fixture(scope='function')
def mocked_endpoints_provider():
    yield [
        Endpoint('a'),
        Endpoint('b'),
        Endpoint('c')
    ]


class TestEndpointsRetryPolicy:
    def test_init_context(self, mocked_endpoints_provider):
        endpoints_retry_policy = EndpointsRetryPolicy(
            endpoints_provider=mocked_endpoints_provider
        )

        mocked_context = {}
        endpoints_retry_policy.init_context(mocked_context)

        assert mocked_context['endpoint'].get_value() == mocked_endpoints_provider[0].get_value()
        assert [
            e.get_value()
            for e in mocked_context['alternative_endpoints']
        ] == [
            e.get_value()
            for e in mocked_endpoints_provider[1:]
        ]

    def test_should_retry(self, mocked_endpoints_provider):
        mocked_attempt = Attempt()

        endpoints_retry_policy = EndpointsRetryPolicy(
            endpoints_provider=mocked_endpoints_provider
        )
        endpoints_retry_policy.init_context(mocked_attempt.context)
        assert endpoints_retry_policy.should_retry(mocked_attempt)

    def test_prepare_retry(self, mocked_endpoints_provider):
        mocked_attempt = Attempt()

        endpoints_retry_policy = EndpointsRetryPolicy(
            endpoints_provider=mocked_endpoints_provider
        )
        endpoints_retry_policy.init_context(mocked_attempt.context)

        actual_tried_endpoints = [
            mocked_attempt.context.get('endpoint')
        ]
        while endpoints_retry_policy.should_retry(mocked_attempt):
            endpoints_retry_policy.prepare_retry(mocked_attempt)
            actual_tried_endpoints.append(mocked_attempt.context.get('endpoint'))

        assert [
            e.get_value() for e in actual_tried_endpoints
        ] == [
            e.get_value() for e in mocked_endpoints_provider
        ]

    def test_skip_init_context(self, mocked_endpoints_provider):
        endpoints_retry_policy = EndpointsRetryPolicy(
            endpoints_provider=mocked_endpoints_provider,
            skip_init_context=True
        )

        mocked_context = {}
        endpoints_retry_policy.init_context(mocked_context)

        assert not mocked_context.get('endpoint')
        assert not mocked_context.get('alternative_endpoints')
