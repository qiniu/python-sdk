from collections import namedtuple
from functools import partial

from qiniu.compat import is_seekable
from qiniu.http.endpoints_retry_policy import EndpointsRetryPolicy
from qiniu.http.region import ServiceName
from qiniu.http.regions_retry_policy import RegionsRetryPolicy
from qiniu.retry.abc import RetryPolicy
from qiniu.retry import Retrier


_TokenExpiredRetryState = namedtuple(
    'TokenExpiredRetryState',
    [
        'retried_times',
        'upload_api_version'
    ]
)


class TokenExpiredRetryPolicy(RetryPolicy):
    def __init__(
        self,
        upload_api_version,
        record_delete_handler,
        record_exists_handler,
        max_retry_times=1
    ):
        """
        Parameters
        ----------
        upload_api_version: str
        record_delete_handler: callable
            `() -> None`
        record_exists_handler: callable
            `() -> bool`
        max_retry_times: int
        """
        self.upload_api_version = upload_api_version
        self.record_delete_handler = record_delete_handler
        self.record_exists_handler = record_exists_handler
        self.max_retry_times = max_retry_times

    def init_context(self, context):
        """
        Parameters
        ----------
        context: dict
        """
        context[self] = _TokenExpiredRetryState(
            retried_times=0,
            upload_api_version=self.upload_api_version
        )

    def should_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: qiniu.retry.Attempt

        Returns
        -------
        bool
        """
        state = attempt.context[self]

        if (
            state.retried_times >= self.max_retry_times or
            not self.record_exists_handler()
        ):
            return False

        if not attempt.result:
            return False

        _ret, resp = attempt.result

        if (
            state.upload_api_version == 'v1' and
            resp.status_code == 701
        ):
            return True

        if (
            state.upload_api_version == 'v2' and
            resp.status_code == 612
        ):
            return True

        return False

    def prepare_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: qiniu.retry.Attempt
        """
        state = attempt.context[self]
        attempt.context[self] = state._replace(retried_times=state.retried_times + 1)

        if not self.record_exists_handler():
            return

        self.record_delete_handler()


class AccUnavailableRetryPolicy(RetryPolicy):
    def __init__(self, on_fallback=None):
        self.on_fallback = on_fallback

    def init_context(self, context):
        pass

    def should_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: qiniu.retry.Attempt

        Returns
        -------
        bool
        """
        if not attempt.result or attempt.context.get('service_name') != ServiceName.UP_ACC:
            return False

        region = attempt.context.get('region')
        if not region:
            return False

        if all(
            not region.services[sn]
            for sn in attempt.context.get('alternative_service_names', [])
        ):
            return False

        _ret, resp = attempt.result

        return resp.status_code == 400 and \
            'transfer acceleration is not configured on this bucket' in (resp.text_body or '')

    def prepare_retry(self, attempt):
        """
        Parameters
        ----------
        attempt: qiniu.retry.Attempt
        """
        endpoints = []
        while not endpoints:
            if not attempt.context.get('alternative_service_names'):
                raise RuntimeError('No alternative service available')
            attempt.context['service_name'] = attempt.context.get('alternative_service_names').pop(0)
            # shallow copy list
            # change to `list.copy` for more readable when min version of python update to >= 3
            endpoints = attempt.context['region'].services.get(attempt.context['service_name'], [])[:]
        attempt.context['alternative_endpoints'] = endpoints
        attempt.context['endpoint'] = attempt.context['alternative_endpoints'].pop(0)
        if self.on_fallback:
            self.on_fallback()


ProgressRecord = namedtuple(
    'ProgressRecorder',
    [
        'upload_api_version',
        'exists',
        'delete'
    ]
)


class ResumableUploadProgress(object):
    def __init__(self, recorder, file_name, key, upload_api_version):
        self.upload_api_version = upload_api_version
        self.exists = partial(recorder.has_upload_record, file_name, key)
        self.delete = partial(recorder.delete_upload_record, file_name, key)
        self.load = partial(recorder.get_upload_record, file_name, key)
        self.save = partial(recorder.set_upload_record, file_name, key)
        self.previous = None

    def reset_for_fallback(self):
        # Keep the original session available if the fallback also fails.
        if self.previous is None:
            self.previous = self.load()
        self.delete()

    def restore_after_failure(self):
        if self.previous is not None:
            self.save(self.previous)


class RetrySavedUploadPolicy(RetryPolicy):
    def __init__(self, progress_record):
        self.progress_record = progress_record

    def init_context(self, context):
        context[self] = False

    def should_retry(self, attempt):
        if attempt.context[self] or not attempt.result:
            return False
        _, response = attempt.result
        return 500 <= response.status_code < 600 and response.need_retry() and self.progress_record.exists()

    def prepare_retry(self, attempt):
        # One retry of the saved session before changing upload endpoints.
        attempt.context[self] = True


def should_retry_upload(attempt, retrier):
    """Permit response-specific recovery before trying another endpoint."""
    _, response = attempt.result
    return response.need_retry() or any(
        policy.should_retry(attempt) for policy in retrier.policies
        if isinstance(policy, (AccUnavailableRetryPolicy, TokenExpiredRetryPolicy))
    )


def retry_resumable_upload(retrier, upload, upload_opts, progress_record):
    data = upload_opts.get('data')
    attempt = None
    succeeded = False
    try:
        for attempt in retrier:
            with attempt:
                upload_opts['up_endpoint'] = attempt.context.get('endpoint')
                attempt.result = upload(**upload_opts)
                ret, response = attempt.result
                succeeded = response.ok() and bool(ret)
                if succeeded or not is_seekable(data) or not should_retry_upload(attempt, retrier):
                    return attempt.result
                data.seek(0)
        if attempt is None:
            raise RuntimeError('Retrier is not working. attempt is None')
        return attempt.result
    finally:
        if progress_record and not succeeded:
            progress_record.restore_after_failure()


def get_default_retrier(
    regions_provider,
    preferred_endpoints_provider=None,
    progress_record=None,
    accelerate_uploading=False
):
    """
    Parameters
    ----------
    regions_provider: Iterable[Region]
    preferred_endpoints_provider: Iterable[Endpoint]
    progress_record: ProgressRecord
    accelerate_uploading: bool

    Returns
    -------
    Retrier
    """
    retry_policies = []
    upload_service_names = [ServiceName.UP]
    reset_progress = None
    reset_for_fallback = None
    if progress_record:
        reset_for_fallback = getattr(progress_record, 'reset_for_fallback', progress_record.delete)

    if accelerate_uploading:
        # Resumable upload records pin the previous endpoint. Start fresh on fallback.
        retry_policies.append(AccUnavailableRetryPolicy(
            on_fallback=reset_for_fallback
        ))
        upload_service_names.insert(0, ServiceName.UP_ACC)

    if progress_record:
        retry_policies.append(TokenExpiredRetryPolicy(
            upload_api_version=progress_record.upload_api_version,
            record_delete_handler=progress_record.delete,
            record_exists_handler=progress_record.exists
        ))
        retry_policies.append(RetrySavedUploadPolicy(progress_record))

        def _reset_progress(_):
            # A different service or region must start without the old upload context.
            reset_for_fallback()

        reset_progress = _reset_progress

    retry_policies += [
        EndpointsRetryPolicy(skip_init_context=True),
        RegionsRetryPolicy(
            regions_provider=regions_provider,
            service_names=upload_service_names,
            preferred_endpoints_provider=preferred_endpoints_provider,
            on_change_endpoint=reset_progress
        )
    ]

    return Retrier(retry_policies)
