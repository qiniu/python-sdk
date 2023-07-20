# -*- coding: utf-8 -*-
import logging

import requests

from .response import ResponseInfo
from .middleware import compose_middleware


class HTTPClient:
    def __init__(self, middlewares=None, send_opts=None):
        self.session = requests.Session()
        self.middlewares = [] if middlewares is None else middlewares
        self.send_opts = {} if send_opts is None else send_opts

    def _wrap_send(self, req, **kwargs):
        resp = self.session.send(req.prepare(), **kwargs)
        return ResponseInfo(resp, None)

    def send_request(self, request, middlewares=None, **kwargs):
        """

        Args:
            request (requests.Request):
                requests.Request 对象

            middlewares (list[qiniu.http.middleware.Middleware] or (list[qiniu.http.middleware.Middleware]) -> list[qiniu.http.middleware.Middleware]):
                仅对本次请求生效的中间件。

                如果传入的是列表，那么会作为追加的中间件拼接到 Client 中间件的后面。

                也可传入函数，获得 Client 中间件的一个副本来做更细的控制。
                例如拼接到 Client 中间件的前面，可以这样使用：

                c.send_request(my_req, middlewares=lambda mws: my_mws + mws)

            kwargs:
                将作为其他参数直接透传给 session.send 方法


        Returns:
            (dict, ResponseInfo): 可拆包的一个元组。
            第一个元素为响应体的 dict，若响应体为 json 的话。
            第二个元素为包装过的响应内容，包括了更多的响应内容。

        """

        # set default values
        middlewares = [] if middlewares is None else middlewares

        # join middlewares and client middlewares
        mw_ls = []
        if callable(middlewares):
            mw_ls = middlewares(self.middlewares.copy())
        elif isinstance(middlewares, list):
            mw_ls = self.middlewares + middlewares

        # send request
        try:
            handle = compose_middleware(
                mw_ls,
                lambda req: self._wrap_send(req, **kwargs)
            )
            resp_info = handle(request)
        except Exception as e:
            return None, ResponseInfo(None, e)

        # if ok try dump response info to dict from json
        if not resp_info.ok():
            return None, resp_info

        try:
            ret = resp_info.json()
        except ValueError:
            logging.debug("response body decode error: %s" % resp_info.text_body)
            ret = {}
        return ret, resp_info

    def get(
        self,
        url,
        params=None,
        auth=None,
        headers=None,
        middlewares=None,
        **kwargs
    ):
        req = requests.Request(
            method='get',
            url=url,
            params=params,
            auth=auth,
            headers=headers
        )
        send_opts = self.send_opts.copy()
        send_opts.update(kwargs)
        send_opts.setdefault("allow_redirects", True)
        return self.send_request(
            req,
            middlewares=middlewares,
            **send_opts
        )

    def post(
        self,
        url,
        data=None,
        files=None,
        auth=None,
        headers=None,
        middlewares=None,
        **kwargs
    ):
        req = requests.Request(
            method='post',
            url=url,
            data=data,
            files=files,
            auth=auth,
            headers=headers
        )
        send_opts = self.send_opts.copy()
        send_opts.update(kwargs)
        return self.send_request(
            req,
            middlewares=middlewares,
            **send_opts
        )

    def put(
        self,
        url,
        data,
        files,
        auth=None,
        headers=None,
        middlewares=None,
        **kwargs
    ):
        req = requests.Request(
            method='put',
            url=url,
            data=data,
            files=files,
            auth=auth,
            headers=headers
        )
        send_opts = self.send_opts.copy()
        send_opts.update(kwargs)
        return self.send_request(
            req,
            middlewares=middlewares,
            **send_opts
        )

    def delete(
        self,
        url,
        params,
        auth=None,
        headers=None,
        middlewares=None,
        **kwargs
    ):
        req = requests.Request(
            method='delete',
            url=url,
            params=params,
            auth=auth,
            headers=headers
        )
        send_opts = self.send_opts.copy()
        send_opts.update(kwargs)
        return self.send_request(
            req,
            middlewares=middlewares,
            **send_opts
        )
