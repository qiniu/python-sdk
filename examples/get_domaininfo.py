# -*- coding: utf-8 -*-
# flake8: noqa

"""
获取指定域名指定时间内的日志链接
"""
import qiniu
from qiniu import DomainManager


# 账户ak，sk
access_key = 'oPQDbCnHhXjZtGZk6ysNYDMrcs7a8Puy_e0mcaL_'
secret_key = 'DzQHHAizEpsr3LqiIfjF8-p2cBi406nR44CYasBx'

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
domain_manager = DomainManager(auth)
domain = ''
ret, info = domain_manager.get_domain(domain)
print(ret)
print(info)