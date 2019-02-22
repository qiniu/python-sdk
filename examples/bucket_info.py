# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

# 需要填写你的 Access Key 和 Secret Key
access_key = ''
secret_key = ''

# 空间名
bucket_name = 'bucket_name'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

ret, info = bucket.bucket_info(bucket_name)
print(info)
