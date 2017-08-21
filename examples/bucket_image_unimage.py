# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

access_key = '...'
secret_key = '...'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

bucket_name = 'Bucket_Name'

key = '...'

image_url = ''

req_host = ''

ret, info = bucket.image(bucket_name, image_url, req_host)
print(info)

ret, info = bucket.unimage(bucket_name, image_url, req_host)
print(info)
