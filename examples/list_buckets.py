# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

# 需要填写你的 Access Key 和 Secret Key
access_key = ''
secret_key = ''

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

# 指定需要列举的区域，填空字符串返回全部空间，为减少响应时间建议填写
# z0:只返回华东区域的空间
# z1:只返回华北区域的空间
# z2:只返回华南区域的空间
# na0:只返回北美区域的空间
# as0:只返回东南亚区域的空间
region = "z0"

ret, info = bucket.list_bucket(region)
print(info)
print(ret)
