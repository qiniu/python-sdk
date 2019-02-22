# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

# 需要填写你的 Access Key 和 Secret Key
access_key = '...'
secret_key = '...'

bucket_name = 'Bucket_Name'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

region = "z0"

ret, info = bucket.mkbucketv2(bucket_name, region)
print(info)
