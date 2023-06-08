# -*- coding: utf-8 -*-
from qiniu.compat import is_py2, is_py3


class ResponseInfo(object):
    """七牛HTTP请求返回信息类

    该类主要是用于获取和解析对七牛发起各种请求后的响应包的header和body。

    Attributes:
        status_code (int): 整数变量，响应状态码
        text_body (str):   字符串变量，响应的body
        req_id (str):      字符串变量，七牛HTTP扩展字段，参考 https://developer.qiniu.com/kodo/3924/common-request-headers
        x_log (str):       字符串变量，七牛HTTP扩展字段，参考 https://developer.qiniu.com/kodo/3924/common-request-headers
        error (str):       字符串变量，响应的错误内容
    """

    def __init__(self, response, exception=None):
        """用响应包和异常信息初始化ResponseInfo类"""
        self.__response = response
        self.exception = exception
        if response is None:
            self.status_code = -1
            self.text_body = None
            self.req_id = None
            self.x_log = None
            self.error = str(exception)
        else:
            self.status_code = response.status_code
            self.text_body = response.text
            self.req_id = response.headers.get('X-Reqid')
            self.x_log = response.headers.get('X-Log')
            if self.status_code >= 400:
                if self.__check_json(response):
                    ret = response.json() if response.text != '' else None
                    if ret is None:
                        self.error = 'unknown'
                    else:
                        self.error = response.text
                else:
                    self.error = response.text
            if self.req_id is None and self.status_code == 200:
                self.error = 'server is not qiniu'

    def ok(self):
        return self.status_code // 100 == 2

    def need_retry(self):
        if 0 < self.status_code < 500:
            return False
        # https://developer.qiniu.com/fusion/kb/1352/the-http-request-return-a-status-code
        if self.status_code in [
            501, 509, 573, 579, 608, 612, 614, 616, 618, 630, 631, 632, 640, 701
        ]:
            return False
        return True

    def connect_failed(self):
        return self.__response is None or self.req_id is None

    def json(self):
        try:
            self.__response.encoding = "utf-8"
            return self.__response.json()
        except Exception:
            return {}

    def __str__(self):
        if is_py2:
            return ', '.join(
                ['%s:%s' % item for item in self.__dict__.items()]).encode('utf-8')
        elif is_py3:
            return ', '.join(
                ['%s:%s' % item for item in self.__dict__.items()])

    def __repr__(self):
        return self.__str__()

    def __check_json(self, response):
        try:
            response.json()
            return True
        except Exception:
            return False
