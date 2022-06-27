# -*- coding: utf-8 -*-
# flake8: noqa

"""
更新cdn证书(可配合let's encrypt 等完成自动证书更新)
"""
import qiniu
from qiniu import DomainManager

# 账户ak，sk
access_key = ''
secret_key = ''

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
domain_manager = DomainManager(auth)

privatekey = "ssl/www.qiniu.com/privkey.pem"
ca = "ssl/www.qiniu.com/fullchain.pem"
domain_name = 'www.qiniu.com'

with open(privatekey, 'r') as f:
    privatekey_str = f.read()

with open(ca, 'r') as f:
    ca_str = f.read()

ret, info = domain_manager.create_sslcert(
    domain_name, domain_name, privatekey_str, ca_str)
print(ret['certID'])

ret, info = domain_manager.put_httpsconf(domain_name, ret['certID'], False)
print(info)
