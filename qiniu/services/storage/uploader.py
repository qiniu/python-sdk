# -*- coding: utf-8 -*-

import os

from qiniu import config
from qiniu.utils import urlsafe_base64_encode, crc32, file_crc32, _file_iter
from qiniu import http


def put_data(
        up_token, key, data, params=None, mime_type='application/octet-stream', check_crc=False, progress_handler=None):
    ''' put data to Qiniu
    If key is None, the server will generate one.
    data may be str or read()able object.
    '''
    crc = crc32(data) if check_crc else None
    return _form_put(up_token, key, data, params, mime_type, crc, False, progress_handler)


def put_file(up_token, key, file_path, params=None, mime_type='application/octet-stream', check_crc=False, progress_handler=None):
    ret = {}
    size = os.stat(file_path).st_size
    with open(file_path, 'rb') as input_stream:
        if size > config._BLOCK_SIZE * 2:
            ret, info = put_stream(up_token, key, input_stream, size, params, mime_type, progress_handler)
        else:
            crc = file_crc32(file_path) if check_crc else None
            ret, info = _form_put(up_token, key, input_stream, params, mime_type, crc, True, progress_handler)
    return ret, info


def _form_put(up_token, key, data, params, mime_type, crc32, is_file=False, progress_handler=None):
    fields = {}
    if params:
        for k, v in params.items():
            fields[k] = str(v)
    if crc32:
        fields['crc32'] = crc32
    if key is not None:
        fields['key'] = key
    fields['token'] = up_token
    url = 'http://' + config.get_default('default_up_host') + '/'
    name = key if key else 'filename'

    r, info = http._post_file(url, data=fields, files={'file': (name, data, mime_type)})
    if r is None and info.need_retry():
        if info.connect_failed:
            url = 'http://' + config.UPBACKUP_HOST + '/'
        if is_file:
            data.seek(0)
        r, info = http._post_file(url, data=fields, files={'file': (name, data, mime_type)})

    return r, info


def put_stream(up_token, key, input_stream, data_size, params=None, mime_type=None, progress_handler=None):
    task = _Resume(up_token, key, input_stream, data_size, params, mime_type, progress_handler)
    return task.upload()


class _Resume(object):

    def __init__(self, up_token, key, input_stream, data_size, params, mime_type, progress_handler):
        self.up_token = up_token
        self.key = key
        self.input_stream = input_stream
        self.size = data_size
        self.params = params
        self.mime_type = mime_type
        self.progress_handler = progress_handler

    def upload(self):
        self.blockStatus = []
        host = config.get_default('default_up_host')
        for block in _file_iter(self.input_stream, config._BLOCK_SIZE):
            length = len(block)
            crc = crc32(block)
            ret, info = self.make_block(block, length, host)
            if ret is None and not info.need_retry:
                return ret, info
            if info.connect_failed:
                host = config.UPBACKUP_HOST
            if info.need_retry or crc != ret['crc32']:
                ret, info = self.make_block(block, length, host)
                if ret is None or crc != ret['crc32']:
                    return ret, info

            self.blockStatus.append(ret)
            if(callable(self.progress_handler)):
                self.progress_handler(((len(self.blockStatus) - 1) * config._BLOCK_SIZE)+length, self.size)
        return self.make_file(host)

    def make_block(self, block, block_size, host):
        url = self.block_url(host, block_size)
        return self.post(url, block)

    def block_url(self, host, size):
        return 'http://{0}/mkblk/{1}'.format(host, size)

    def file_url(self, host):
        url = ['http://{0}/mkfile/{1}'.format(host, self.size)]

        if self.mime_type:
            url.append('mimeType/{0}'.format(urlsafe_base64_encode(self.mime_type)))

        if self.key is not None:
            url.append('key/{0}'.format(urlsafe_base64_encode(self.key)))

        if self.params:
            for k, v in self.params.items():
                url.append('{0}/{1}'.format(k, urlsafe_base64_encode(v)))

        url = '/'.join(url)
        return url

    def make_file(self, host):
        url = self.file_url(host)
        body = ','.join([status['ctx'] for status in self.blockStatus])
        return self.post(url, body)

    def post(self, url, data):
        return http._post_with_token(url, data, self.up_token)
