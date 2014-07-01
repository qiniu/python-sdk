# -*- coding: utf-8 -*-
from .. import conf
from .. import rpc


class Client(rpc.Client):
    up_token = None

    def __init__(self, up_token, host=None):
        if host is None:
            host = conf.UP_HOST
        if host.startswith("http://"):
            host = host[7:]
        self.up_token = up_token
        super(Client, self).__init__(host)

    def round_tripper(self, method, path, body, header={}):
        header["Authorization"] = "UpToken %s" % self.up_token
        return super(Client, self).round_tripper(method, path, body, header)
