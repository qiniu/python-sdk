from qiniu.compat import urlparse

from .base import Middleware


class RetryDomainsMiddleware(Middleware):
    def __init__(self, backup_domains, max_retry_times=2):
        """
        Args:
            backup_domains (list[str]):
            max_retry_times (int):
        """
        self.backup_domains = backup_domains
        self.max_retry_times = max_retry_times

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

    def __call__(self, request, nxt):
        resp, err = None, None
        url_parse_result = urlparse(request.url)

        for backup_domain in [str(url_parse_result.hostname)] + self.backup_domains:
            request.url = RetryDomainsMiddleware._get_changed_url(request.url, backup_domain)
            self.retried_times = 0

            while (resp is None or not resp.ok) and self.retried_times < self.max_retry_times:
                resp, err = RetryDomainsMiddleware._try_nxt(request, nxt)
                self.retried_times += 1
                if err is None and (resp is not None and resp.ok):
                    return resp

        if err is not None:
            raise err

        return resp
