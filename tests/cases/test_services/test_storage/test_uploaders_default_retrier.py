import pytest

import os

from qiniu.http.region import ServiceName, Region
from qiniu.retry import Attempt
from qiniu.services.storage.uploaders._default_retrier import (
    ProgressRecord,
    TokenExpiredRetryPolicy,
    AccUnavailableRetryPolicy
)


@pytest.fixture(
    scope='function',
    params=[
        {'api_version': 'v1'},
        {'api_version': 'v2'}
    ]
)
def fake_progress_record(request):
    api_version = request.param.get('api_version')
    file_path = os.path.join(os.getcwd(), 'fake-progress-record')

    with open(file_path, 'w'):
        pass

    def _delete():
        try:
            os.remove(file_path)
        except OSError:
            pass

    def _exists():
        return os.path.exists(file_path)

    yield ProgressRecord(
        upload_api_version=api_version,
        exists=_exists,
        delete=_delete
    )

    _delete()


class MockResponse:
    def __init__(self, status_code, text_body=None):
        self.status_code = status_code
        self.text_body = text_body


class TestTokenExpiredRetryPolicy:
    def test_should_retry(self, fake_progress_record):
        policy = TokenExpiredRetryPolicy(
            upload_api_version=fake_progress_record.upload_api_version,
            record_delete_handler=fake_progress_record.delete,
            record_exists_handler=fake_progress_record.exists
        )

        attempt = Attempt()
        policy.init_context(attempt.context)

        if fake_progress_record.upload_api_version == 'v1':
            mocked_resp = MockResponse(status_code=701)
        else:
            mocked_resp = MockResponse(status_code=612)
        attempt.result = (None, mocked_resp)

        assert policy.should_retry(attempt)

    def test_should_not_retry_by_no_result(self, fake_progress_record):
        policy = TokenExpiredRetryPolicy(
            upload_api_version=fake_progress_record.upload_api_version,
            record_delete_handler=fake_progress_record.delete,
            record_exists_handler=fake_progress_record.exists
        )
        attempt = Attempt()
        policy.init_context(attempt.context)

        assert not policy.should_retry(attempt)

    def test_should_not_retry_by_default_max_retried_times(self, fake_progress_record):
        policy = TokenExpiredRetryPolicy(
            upload_api_version=fake_progress_record.upload_api_version,
            record_delete_handler=fake_progress_record.delete,
            record_exists_handler=fake_progress_record.exists
        )
        attempt = Attempt()
        policy.init_context(attempt.context)
        if fake_progress_record.upload_api_version == 'v1':
            mocked_resp = MockResponse(status_code=701)
        else:
            mocked_resp = MockResponse(status_code=612)
        attempt.result = (None, mocked_resp)
        attempt.context[policy] = attempt.context[policy]._replace(retried_times=1)

        assert not policy.should_retry(attempt)

    def test_should_not_retry_by_file_no_exists(self, fake_progress_record):
        policy = TokenExpiredRetryPolicy(
            upload_api_version=fake_progress_record.upload_api_version,
            record_delete_handler=fake_progress_record.delete,
            record_exists_handler=fake_progress_record.exists
        )

        attempt = Attempt()
        policy.init_context(attempt.context)
        if fake_progress_record.upload_api_version == 'v1':
            mocked_resp = MockResponse(status_code=701)
        else:
            mocked_resp = MockResponse(status_code=612)
        attempt.result = (None, mocked_resp)
        fake_progress_record.delete()

        assert not policy.should_retry(attempt)

    def test_prepare_retry(self, fake_progress_record):
        policy = TokenExpiredRetryPolicy(
            upload_api_version=fake_progress_record.upload_api_version,
            record_delete_handler=fake_progress_record.delete,
            record_exists_handler=fake_progress_record.exists
        )

        attempt = Attempt()
        policy.init_context(attempt.context)
        if fake_progress_record.upload_api_version == 'v1':
            mocked_resp = MockResponse(status_code=701)
        else:
            mocked_resp = MockResponse(status_code=612)
        attempt.result = (None, mocked_resp)

        policy.prepare_retry(attempt)

        assert not fake_progress_record.exists()


class TestAccUnavailableRetryPolicy:
    def test_should_retry(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()

        attempt.context['service_name'] = ServiceName.UP_ACC
        attempt.context['alternative_service_names'] = [ServiceName.UP]
        attempt.context['region'] = Region.from_region_id('z0')

        mocked_resp = MockResponse(
            status_code=400,
            text_body='{"error":"transfer acceleration is not configured on this bucket"}'
        )
        attempt.result = (None, mocked_resp)

        assert policy.should_retry(attempt)

    def test_should_not_retry_by_no_result(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()

        attempt.context['service_name'] = ServiceName.UP_ACC
        attempt.context['alternative_service_names'] = [ServiceName.UP]
        attempt.context['region'] = Region.from_region_id('z0')

        assert not policy.should_retry(attempt)

    def test_should_not_retry_by_no_alternative_services(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()

        attempt.context['service_name'] = ServiceName.UP
        attempt.context['alternative_service_names'] = []
        attempt.context['region'] = Region.from_region_id('z0')

        mocked_resp = MockResponse(
            status_code=400,
            text_body='{"error":"transfer acceleration is not configured on this bucket"}'
        )
        attempt.result = (None, mocked_resp)

        assert not policy.should_retry(attempt)

    def test_should_not_retry_by_no_alternative_endpoints(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()

        attempt.context['service_name'] = ServiceName.UP_ACC
        attempt.context['alternative_service_names'] = [ServiceName.UP]
        attempt.context['region'] = Region.from_region_id('z0')
        attempt.context['region'].services[ServiceName.UP] = []

        mocked_resp = MockResponse(
            status_code=400,
            text_body='{"error":"transfer acceleration is not configured on this bucket"}'
        )
        attempt.result = (None, mocked_resp)

        assert not policy.should_retry(attempt)

    def test_should_not_retry_by_other_error(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()

        attempt.context['service_name'] = ServiceName.UP_ACC
        attempt.context['alternative_service_names'] = [ServiceName.UP]
        attempt.context['region'] = Region.from_region_id('z0')

        mocked_resp = MockResponse(
            status_code=400,
            text_body='{"error":"Bad Request"}'
        )
        attempt.result = (None, mocked_resp)

        assert not policy.should_retry(attempt)

    def test_prepare_retry(self):
        policy = AccUnavailableRetryPolicy()
        attempt = Attempt()
        region = Region.from_region_id('z0')

        attempt.context['service_name'] = ServiceName.UP_ACC
        attempt.context['alternative_service_names'] = [ServiceName.UP]
        attempt.context['region'] = region

        mocked_resp = MockResponse(
            status_code=400,
            text_body='{"error":"transfer acceleration is not configured on this bucket"}'
        )
        attempt.result = (None, mocked_resp)

        policy.prepare_retry(attempt)

        assert attempt.context['service_name'] == ServiceName.UP
        assert (
            [attempt.context['endpoint']] + attempt.context['alternative_endpoints']
            ==
            region.services[ServiceName.UP]
        )
