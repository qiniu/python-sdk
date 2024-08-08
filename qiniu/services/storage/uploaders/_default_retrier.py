from collections import namedtuple

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
    def __init__(self):
        pass

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
        if not attempt.result:
            return False

        region = attempt.context.get('region')
        if not region:
            return False

        if all(
            not region.services[sn]
            for sn in attempt.context.get('alternative_service_names')
        ):
            return False

        _ret, resp = attempt.result

        return resp.status_code == 400 and \
            'transfer acceleration is not configured on this bucket' in resp.text_body

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


ProgressRecord = namedtuple(
    'ProgressRecorder',
    [
        'upload_api_version',
        'exists',
        'delete'
    ]
)


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

    if accelerate_uploading:
        retry_policies.append(AccUnavailableRetryPolicy())
        upload_service_names.insert(0, ServiceName.UP_ACC)

    if progress_record:
        retry_policies.append(TokenExpiredRetryPolicy(
            upload_api_version=progress_record.upload_api_version,
            record_delete_handler=progress_record.delete,
            record_exists_handler=progress_record.exists
        ))

    retry_policies += [
        EndpointsRetryPolicy(skip_init_context=True),
        RegionsRetryPolicy(
            regions_provider=regions_provider,
            service_names=upload_service_names,
            preferred_endpoints_provider=preferred_endpoints_provider,
            on_change_region=lambda _: progress_record.delete()
        )
    ]

    return Retrier(retry_policies)
