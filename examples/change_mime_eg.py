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

ret, info = bucket.change_mime(bucket_name, key, 'image/jpg')
print(info)
assert info.status_code == 200
