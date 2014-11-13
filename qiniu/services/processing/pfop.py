# -*- coding: utf-8 -*-

from qiniu import config
from qiniu import http


class PersistentFop(object):

    def __init__(self, auth, bucket, pipeline=None, notify_url=None):
        self.auth = auth
        self.bucket = bucket
        self.pipeline = pipeline
        self.notify_url = notify_url

    def execute(self, key, fops, force=None):
        ops = ';'.join(fops)
        data = {'bucket': self.bucket, 'key': key, 'fops': ops}
        if self.pipeline:
            data['pipeline'] = self.pipeline
        if self.notify_url:
            data['notifyURL'] = self.notify_url
        if force == 1:
            data['force'] = 1

        url = 'http://{0}/pfop'.format(config.API_HOST)
        return http._post_with_auth(url, data, self.auth)
