# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth
from qiniu import BucketManager


access_key = ''
secret_key = ''

q = Auth(access_key, secret_key)
bucket = BucketManager(q)
bucket_name = '13'
key = 'fb8539c39f65d74b4e70db9133c1e9d5.mp4'
ret,info = bucket.restoreAr(bucket_name,key,3)
print(ret)
print(info)

