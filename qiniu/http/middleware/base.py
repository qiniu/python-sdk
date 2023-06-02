# -*- coding: utf-8 -*-
from functools import reduce


def compose_middleware(middlewares, handle):
    """
    Args:
        middlewares (list[Middleware]): Middlewares
        handle ((requests.Request) -> qiniu.http.response.ResponseInfo): The send request handle

    Returns:
        (requests.Request) -> qiniu.http.response.ResponseInfo: Composed handle

    """
    middlewares.reverse()

    return reduce(
        lambda h, mw:
            lambda req: mw(req, h),
        middlewares,
        handle
    )


class Middleware:
    def __call__(self, request, nxt):
        """
        Args:
            request (requests.Request):
            nxt ((requests.Request) -> qiniu.http.response.ResponseInfo):

        Returns:
            requests.Response:

        """
        raise NotImplementedError('{0}.__call__ method is not implemented yet'.format(type(self)))
