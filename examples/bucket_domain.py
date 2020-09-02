# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

"""
获取空间绑定的加速域名
https://developer.qiniu.com/kodo/api/3949/get-the-bucket-space-domain
"""

# 七牛账号的 公钥和私钥
access_key = '<access_key>'
secret_key = '<secret_key>'

# 空间名
bucket_name = ''

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

ret, info = bucket.bucket_domain(bucket_name)
print(info)
