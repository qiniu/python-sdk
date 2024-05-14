# -*- coding: utf-8 -*-
import base64
from datetime import datetime
import hmac
import os
import time
from hashlib import sha1
from requests.auth import AuthBase
from .compat import urlparse, json, b
from .utils import urlsafe_base64_encode, canonical_mime_header_key

# 上传策略，参数规格详见
# https://developer.qiniu.com/kodo/manual/1206/put-policy
# the `str()` prevent implicit concatenation of string. DON'T remove it.
# for example, avoid you lost comma at the end of line in middle.
_policy_fields = {
    str('callbackUrl'),  # 回调URL
    str('callbackBody'),  # 回调Body
    str('callbackHost'),  # 回调URL指定的Host
    str('callbackBodyType'),  # 回调Body的Content-Type
    str('callbackFetchKey'),  # 回调FetchKey模式开关

    str('returnUrl'),  # 上传端的303跳转URL
    str('returnBody'),  # 上传端简单反馈获取的Body

    str('endUser'),  # 回调时上传端标识
    str('saveKey'),  # 自定义资源名
    str('forceSaveKey'),  # saveKey的优先级设置。为 true 时，saveKey不能为空，会忽略客户端指定的key，强制使用saveKey进行文件命名。参数不设置时，默认值为false
    str('insertOnly'),  # 插入模式开关

    str('detectMime'),  # MimeType侦测开关
    str('mimeLimit'),  # MimeType限制
    str('fsizeLimit'),  # 上传文件大小限制
    str('fsizeMin'),  # 上传文件最少字节数
    str('keylimit'),  # 设置允许上传的key列表，字符串数组类型，数组长度不可超过20个，如果设置了这个字段，上传时必须提供key

    str('persistentOps'),  # 持久化处理操作
    str('persistentNotifyUrl'),  # 持久化处理结果通知URL
    str('persistentPipeline'),  # 持久化处理独享队列
    str('persistentType'),  # 指定是否开始闲时任务
    str('deleteAfterDays'),  # 文件多少天后自动删除
    str('fileType'),  # 文件的存储类型，0为标准存储，1为低频存储，2为归档存储，3为深度归档存储，4为归档直读存储
    str('isPrefixalScope'),  # 指定上传文件必须使用的前缀

    str('transform'),  # deprecated
    str('transformFallbackKey'),  # deprecated
    str('transformFallbackMode'),  # deprecated
}


class Auth(object):
    """七牛安全机制类

    该类主要内容是七牛上传凭证、下载凭证、管理凭证三种凭证的签名接口的实现，以及回调验证。

    Attributes:
        __access_key: 账号密钥对中的accessKey，详见 https://portal.qiniu.com/user/key
        __secret_key: 账号密钥对重的secretKey，详见 https://portal.qiniu.com/user/key
    """

    def __init__(self, access_key, secret_key, disable_qiniu_timestamp_signature=None):
        """初始化Auth类"""
        self.__checkKey(access_key, secret_key)
        self.__access_key = access_key
        self.__secret_key = b(secret_key)
        self.disable_qiniu_timestamp_signature = disable_qiniu_timestamp_signature

    def get_access_key(self):
        return self.__access_key

    def get_secret_key(self):
        return self.__secret_key

    def __token(self, data):
        data = b(data)
        hashed = hmac.new(self.__secret_key, data, sha1)
        return urlsafe_base64_encode(hashed.digest())

    def token(self, data):
        return '{0}:{1}'.format(self.__access_key, self.__token(data))

    def token_with_data(self, data):
        data = urlsafe_base64_encode(data)
        return '{0}:{1}:{2}'.format(
            self.__access_key, self.__token(data), data)

    def token_of_request(self, url, body=None, content_type=None):
        """带请求体的签名（本质上是管理凭证的签名）

        Args:
            url:          待签名请求的url
            body:         待签名请求的body
            content_type: 待签名请求的body的Content-Type

        Returns:
            管理凭证
        """
        parsed_url = urlparse(url)
        query = parsed_url.query
        path = parsed_url.path
        data = path
        if query != '':
            data = ''.join([data, '?', query])
        data = ''.join([data, "\n"])

        if body:
            mimes = [
                'application/x-www-form-urlencoded'
            ]
            if content_type in mimes:
                data += body

        return '{0}:{1}'.format(self.__access_key, self.__token(data))

    @staticmethod
    def __checkKey(access_key, secret_key):
        if not (access_key and secret_key):
            raise ValueError('invalid key')

    def private_download_url(self, url, expires=3600):
        """生成私有资源下载链接

        Args:
            url:     私有空间资源的原始URL
            expires: 下载凭证有效期，默认为3600s

        Returns:
            私有资源的下载链接
        """
        deadline = int(time.time()) + expires
        if '?' in url:
            url += '&'
        else:
            url += '?'
        url = '{0}e={1}'.format(url, str(deadline))

        token = self.token(url)
        return '{0}&token={1}'.format(url, token)

    def upload_token(
            self,
            bucket,
            key=None,
            expires=3600,
            policy=None,
            strict_policy=True):
        """生成上传凭证

        Args:
            bucket:  上传的空间名
            key:     上传的文件名，默认为空
            expires: 上传凭证的过期时间，默认为3600s
            policy:  上传策略，默认为空
            strict_policy:  严格模式，将校验 policy 字段，默认为 True

        Returns:
            上传凭证
        """
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

    @staticmethod
    def up_token_decode(up_token):
        up_token_list = up_token.split(':')
        ak = up_token_list[0]
        sign = base64.urlsafe_b64decode(up_token_list[1])
        decode_policy = base64.urlsafe_b64decode(up_token_list[2])
        decode_policy = decode_policy.decode('utf-8')
        dict_policy = json.loads(decode_policy)
        return ak, sign, dict_policy

    @staticmethod
    def get_bucket_name(up_token):
        _, _, policy = Auth.up_token_decode(up_token)
        if not policy or not policy['scope']:
            return None
        return policy['scope'].split(':', 1)[0]

    def __upload_token(self, policy):
        data = json.dumps(policy, separators=(',', ':'))
        return self.token_with_data(data)

    def verify_callback(
        self,
        origin_authorization,
        url,
        body,
        content_type='application/x-www-form-urlencoded',
        method='GET',
        headers=None
    ):
        """
        Qbox 回调验证

        Parameters
        ----------
        origin_authorization: str
            回调时请求 Header 中的 Authorization 字段
        url: str
            回调请求的 url
        body: str
            回调请求的 body
        content_type: str
            回调请求的 Content-Type
        method: str
            回调请求的 method，Qiniu 签名必须传入，默认 GET
        headers: dict
            回调请求的 headers，Qiniu 签名必须传入，默认为空字典

        Returns
        -------
        bool
            返回 True 表示验证成功，返回 False 表示验证失败
        """
        if headers is None:
            headers = {}

        # 兼容 Qiniu 签名
        if origin_authorization.startswith("Qiniu"):
            qn_auth = QiniuMacAuth(
                access_key=self.__access_key,
                secret_key=self.__secret_key,
                disable_qiniu_timestamp_signature=True
            )
            return qn_auth.verify_callback(
                origin_authorization,
                url=url,
                body=body,
                content_type=content_type,
                method=method,
                headers=headers
            )

        token = self.token_of_request(url, body, content_type)
        authorization = 'QBox {0}'.format(token)
        return origin_authorization == authorization

    @staticmethod
    def __copy_policy(policy, to, strict_policy):
        for k, v in policy.items():
            if (not strict_policy) or k in _policy_fields:
                to[k] = v


class RequestsAuth(AuthBase):
    def __init__(self, auth):
        self.auth = auth

    def __call__(self, r):
        if r.body is not None and r.headers['Content-Type'] == 'application/x-www-form-urlencoded':
            token = self.auth.token_of_request(
                r.url, r.body, 'application/x-www-form-urlencoded')
        else:
            token = self.auth.token_of_request(r.url)
        r.headers['Authorization'] = 'QBox {0}'.format(token)
        return r


class QiniuMacAuth(object):
    """
    Sign Requests

    Attributes:
        __access_key
        __secret_key

    http://kirk-docs.qiniu.com/apidocs/#TOC_325b437b89e8465e62e958cccc25c63f
    """

    def __init__(self, access_key, secret_key, disable_qiniu_timestamp_signature=None):
        self.qiniu_header_prefix = "X-Qiniu-"
        self.__checkKey(access_key, secret_key)
        self.__access_key = access_key
        self.__secret_key = b(secret_key)
        self.disable_qiniu_timestamp_signature = disable_qiniu_timestamp_signature

    def __token(self, data):
        data = b(data)
        hashed = hmac.new(self.__secret_key, data, sha1)
        return urlsafe_base64_encode(hashed.digest())

    @property
    def should_sign_with_timestamp(self):
        if self.disable_qiniu_timestamp_signature is not None:
            return not self.disable_qiniu_timestamp_signature
        if os.getenv('DISABLE_QINIU_TIMESTAMP_SIGNATURE', '').lower() == 'true':
            return False
        return True

    def token_of_request(
            self,
            method,
            host,
            url,
            qheaders,
            content_type=None,
            body=None):
        """
        <Method> <PathWithRawQuery>
        Host: <Host>
        Content-Type: <ContentType>
        [<X-Qiniu-*> Headers]

        [<Body>] #这里的 <Body> 只有在 <ContentType> 存在且不为 application/octet-stream 时才签进去。

        """
        parsed_url = urlparse(url)
        netloc = parsed_url.netloc
        path = parsed_url.path
        query = parsed_url.query

        if not host:
            host = netloc

        path_with_query = path
        if query != '':
            path_with_query = ''.join([path_with_query, '?', query])
        data = ''.join([
            "%s %s" % (method, path_with_query),
            "\n",
            "Host: %s" % host
        ])

        if content_type:
            data += "\n"
            data += "Content-Type: %s" % content_type

        if qheaders:
            data += "\n"
            data += qheaders

        data += "\n\n"

        if content_type and content_type != "application/octet-stream" and body:
            if isinstance(body, bytes):
                data += body.decode(encoding='UTF-8')
            else:
                data += body
        return '{0}:{1}'.format(self.__access_key, self.__token(data))

    def qiniu_headers(self, headers):
        qiniu_fields = [
            key for key in headers
            if key.startswith(self.qiniu_header_prefix) and len(key) > len(self.qiniu_header_prefix)
        ]
        return '\n'.join([
            '%s: %s' % (canonical_mime_header_key(key), headers.get(key)) for key in sorted(qiniu_fields)
        ])

    def verify_callback(
        self,
        origin_authorization,
        url,
        body,
        content_type='application/x-www-form-urlencoded',
        method='GET',
        headers=None
    ):
        """
        Qiniu 回调验证

        Parameters
        ----------
        origin_authorization: str
            回调时请求 Header 中的 Authorization 字段
        url: str
            回调请求的 url
        body: str
            回调请求的 body
        content_type: str
            回调请求的 Content-Type
        method: str
            回调请求的 Method
        headers: dict
            回调请求的 headers

        Returns
        -------

        """
        if headers is None:
            headers = {}
        token = self.token_of_request(
            method=method,
            host=headers.get('Host', None),
            url=url,
            qheaders=self.qiniu_headers(headers),
            content_type=content_type,
            body=body
        )
        authorization = 'Qiniu {0}'.format(token)
        return origin_authorization == authorization

    @staticmethod
    def __checkKey(access_key, secret_key):
        if not (access_key and secret_key):
            raise ValueError('QiniuMacAuthSign : Invalid key')


class QiniuMacRequestsAuth(AuthBase):
    """
    Attributes:
        auth (QiniuMacAuth):
    """
    def __init__(self, auth):
        """
        Args:
            auth (QiniuMacAuth):
        """
        self.auth = auth

    def __call__(self, r):
        if r.headers.get('Content-Type', None) is None:
            r.headers['Content-Type'] = 'application/x-www-form-urlencoded'

        if self.auth.should_sign_with_timestamp:
            x_qiniu_date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            r.headers['X-Qiniu-Date'] = x_qiniu_date

        token = self.auth.token_of_request(
            r.method,
            r.headers.get('Host', None),
            r.url,
            self.auth.qiniu_headers(r.headers),
            r.headers.get('Content-Type', None),
            r.body
        )
        r.headers['Authorization'] = 'Qiniu {0}'.format(token)
        return r
