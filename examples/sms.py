# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import QiniuMacAuth
from qiniu import Sms


access_key = 'bjtWBQXrcxgo7HWwlC_bgHg81j352_GhgBGZPeOW'
secret_key = 'pCav6rTslxP2SIFg0XJmAw53D9PjWEcuYWVdUqAf'

# 初始化Auth状态
q = QiniuMacAuth(access_key, secret_key)

# 初始化Sms
sms = Sms(q)

"""
#创建签名
signature = 'abs'
source = 'website'
req, info = sms.createSignature(signature, source)
print(req,info)
"""

"""
#查询签名
audit_status = ''
page = 1
page_size = 20
req, info = sms.querySignature(audit_status, page, page_size)
print(req, info)
"""

"""
编辑签名
id = 1136530250662940672
signature = 'sssss'
req, info = sms.updateSignature(id, signature)
print(req, info)
"""

"""
#删除签名
signature_id= 1136530250662940672
req, info = sms.deleteSignature(signature_id)
print(req, info)
"""

"""
#创建模版
name = '06-062-test'
template = '${test}'
type = 'notification'
description = '就测试啊'
signature_id = '1131464448834277376'
req, info = sms.createTemplate(name, template, type, description, signature_id)
print(req, info)
"""

"""
#查询模版
audit_status = ''
page = 1
page_size = 20
req, info = sms.queryTemplate(audit_status, page, page_size)
print(req, info)
"""

"""
#编辑模版
template_id = '1136589777022226432'
name = '06-06-test'
template = 'hi,你好'
description = '就测试啊'
signature_id = '1131464448834277376'
req, info = sms.updateTemplate(template_id, name, template, description, signature_id)
print(info)
"""

"""
#删除模版
template_id = '1136589777022226432'
req, info = sms.deleteTemplate(template_id)
print(req, info)
"""

"""
#发送短信
"""
template_id	= ''
mobiles	= []
parameters	= {}
req, info = sms.sendMessage(template_id, mobiles, parameters)
print(req, info)




