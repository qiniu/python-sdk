# -*- coding: utf-8 -*-
from functools import reduce


def compose_middleware(middlewares, handle):
    """
    Args:
        middlewares (list[Middleware]): Middlewares
        handle ((requests.Request) -> requests.Response): The send request handle

    Returns:
        (requests.Request) -> requests.Response: Composed handle

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
            nxt ((requests.Request) -> requests.Response):

        Returns:
            requests.Response:

        """
        raise NotImplementedError('{0}.__call__ method is not implemented yet'.format(type(self)))
