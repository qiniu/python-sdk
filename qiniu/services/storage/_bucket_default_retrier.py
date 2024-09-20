from qiniu.http.endpoints_retry_policy import EndpointsRetryPolicy
from qiniu.http.regions_retry_policy import RegionsRetryPolicy
from qiniu.retry import Retrier


def get_default_retrier(
    regions_provider,
    service_names,
    preferred_endpoints_provider=None,
):
    if not service_names:
        raise ValueError('service_names should not be empty')

    retry_policies = [
        EndpointsRetryPolicy(
            skip_init_context=True
        ),
        RegionsRetryPolicy(
            regions_provider=regions_provider,
            service_names=service_names,
            preferred_endpoints_provider=preferred_endpoints_provider
        )
    ]

    return Retrier(retry_policies)
