# -*- coding: utf-8 -*-

import hmac
import time
from hashlib import sha1

from requests.auth import AuthBase

from .compat import urlparse, json, b
from .utils import urlsafe_base64_encode


_policy_fields = set([
    'callbackUrl',
    'callbackBody',
    'callbackHost',
    'callbackBodyType',
    'callbackFetchKey',

    'returnUrl',
    'returnBody',

    'endUser',
    'saveKey',
    'insertOnly',

    'detectMime',
    'mimeLimit',
    'fsizeLimit',

    'persistentOps',
    'persistentNotifyUrl',
    'persistentPipeline',
])

_deprecated_policy_fields = set([
    'asyncOps'
])


class Auth(object):

    def __init__(self, access_key, secret_key):
        self.__checkKey(access_key, secret_key)
        self.__access_key, self.__secret_key = access_key, secret_key
        self.__secret_key = b(self.__secret_key)

    def __token(self, data):
        data = b(data)
        hashed = hmac.new(self.__secret_key, data, sha1)
        return urlsafe_base64_encode(hashed.digest())

    def token(self, data):
        return '{0}:{1}'.format(self.__access_key, self.__token(data))

    def token_with_data(self, data):
        data = urlsafe_base64_encode(data)
        return '{0}:{1}:{2}'.format(self.__access_key, self.__token(data), data)

    def token_of_request(self, url, body=None, content_type=None):
        parsed_url = urlparse(url)
        query = parsed_url.query
        path = parsed_url.path
        data = path
        if query != '':
            data = ''.join([data, '?', query])
        data = ''.join([data, "\n"])

        if body:
            mimes = [
                'application/x-www-form-urlencoded',
                'application/json'
            ]
            if content_type in mimes:
                data += body

        return '{0}:{1}'.format(self.__access_key, self.__token(data))

    @staticmethod
    def __checkKey(access_key, secret_key):
        if not (access_key and secret_key):
            raise ValueError('invalid key')

    def private_download_url(self, url, expires=3600):
        '''
         *  return private url
        '''

        deadline = int(time.time()) + expires
        if '?' in url:
            url += '&'
        else:
            url += '?'
        url = '{0}e={1}'.format(url, str(deadline))

        token = self.token(url)
        return '{0}&token={1}'.format(url, token)

    def upload_token(self, bucket, key=None, expires=3600, policy=None, strict_policy=True):
        if bucket is None or bucket == '':
            raise ValueError('invalid bucket name')

        scope = bucket
        if key is not None:
            scope = '{0}:{1}'.format(bucket, key)

        args = dict(
            scope=scope,
            deadline=int(time.time()) + expires,
        )

        if policy is not None:
            self.__copy_policy(policy, args, strict_policy)

        return self.__upload_token(args)

    def __upload_token(self, policy):
        data = json.dumps(policy, separators=(',', ':'))
        return self.token_with_data(data)

    def verify_callback(self, origin_authorization, url, body, content_type='application/x-www-form-urlencoded'):
        token = self.token_of_request(url, body, content_type)
        authorization = 'QBox {0}'.format(token)
        return origin_authorization == authorization

    @staticmethod
    def __copy_policy(policy, to, strict_policy):
        for k, v in policy.items():
            if k in _deprecated_policy_fields:
                raise ValueError(k + ' has deprecated')
            if (not strict_policy) or k in _policy_fields:
                to[k] = v


class RequestsAuth(AuthBase):
    def __init__(self, auth):
        self.auth = auth

    def __call__(self, r):
        token = None
        if r.body is not None and r.headers['Content-Type'] == 'application/x-www-form-urlencoded':
            token = self.auth.token_of_request(r.url, r.body, 'application/x-www-form-urlencoded')
        else:
            token = self.auth.token_of_request(r.url)
        r.headers['Authorization'] = 'QBox {0}'.format(token)
        return r
