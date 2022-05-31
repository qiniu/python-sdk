# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth
from qiniu import BucketManager

access_key = '...'
secret_key = '...'

# 初始化Auth状态
q = Auth(access_key, secret_key)

# 初始化BucketManager
bucket = BucketManager(q)

# 要获取域名的空间名
bucket_name = 'Bucket_Name'

# 获取空间绑定的域名列表
ret, info = bucket.list_domains(bucket_name)
print(ret)
print(info)
