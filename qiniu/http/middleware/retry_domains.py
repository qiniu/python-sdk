from qiniu.compat import urlparse

from .base import Middleware


class RetryDomainsMiddleware(Middleware):
    def __init__(self, backup_domains, max_retry_times=2, retry_condition=None):
        """
        Args:
            backup_domains (list[str]):
            max_retry_times (int):
            retry_condition ((requests.Response or None, requests.Request)->bool):
        """
        self.backup_domains = backup_domains
        self.max_retry_times = max_retry_times
        self.retry_condition = retry_condition

        self.retried_times = 0

    @staticmethod
    def _get_changed_url(url, domain):
        url_parse_result = urlparse(url)

        backup_netloc = ''
        has_user = False
        if url_parse_result.username is not None:
            backup_netloc += url_parse_result.username
            has_user = True
        if url_parse_result.password is not None:
            backup_netloc += url_parse_result.password
            has_user = True
        if has_user:
            backup_netloc += '@'
        backup_netloc += domain
        if url_parse_result.port is not None:
            backup_netloc += ':' + str(url_parse_result.port)

        # the _replace is a public method. start with `_` just to prevent conflicts with field names
        # see namedtuple docs
        url_parse_result = url_parse_result._replace(
            netloc=backup_netloc
        )

        return url_parse_result.geturl()

    @staticmethod
    def _try_nxt(request, nxt):
        resp = None
        err = None
        try:
            resp = nxt(request)
        except Exception as e:
            err = e
        return resp, err

    def _should_retry(self, resp, req):
        if callable(self.retry_condition):
            return self.retry_condition(resp, req)

        return resp is None or resp.need_retry()

    def __call__(self, request, nxt):
        resp_info, err = None, None
        url_parse_result = urlparse(request.url)

        for backup_domain in [str(url_parse_result.hostname)] + self.backup_domains:
            request.url = RetryDomainsMiddleware._get_changed_url(request.url, backup_domain)
            self.retried_times = 0

            while self.retried_times < self.max_retry_times:
                resp_info, err = RetryDomainsMiddleware._try_nxt(request, nxt)
                self.retried_times += 1
                if not self._should_retry(resp_info, request):
                    if err is not None:
                        raise err
                    return resp_info

        if err is not None:
            raise err

        return resp_info
