from qiniu.retry.abc import RetryPolicy


class EndpointsRetryPolicy(RetryPolicy):
    def __init__(self, endpoints_provider=None, skip_init_context=False):
        self.endpoints_provider = endpoints_provider if endpoints_provider else []
        self.skip_init_context = skip_init_context

    def init_context(self, context):
        if self.skip_init_context:
            return
        context['alternative_endpoints'] = list(self.endpoints_provider)
        if not context['alternative_endpoints']:
            raise ValueError('There isn\'t available endpoint')
        context['endpoint'] = context['alternative_endpoints'].pop(0)

    def should_retry(self, attempt):
        return len(attempt.context['alternative_endpoints']) > 0

    def prepare_retry(self, attempt):
        if not attempt.context['alternative_endpoints']:
            raise Exception('There isn\'t available endpoint for next try')
        attempt.context['endpoint'] = attempt.context['alternative_endpoints'].pop(0)
