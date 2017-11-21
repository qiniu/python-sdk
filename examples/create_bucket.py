# -*- coding: utf-8 -*-
"""
创建存储空间
"""

from qiniu import Auth
from qiniu import BucketManager


access_key = '...'
secret_key = '...'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

bucket_name = 'Bucket_Name'

# "填写存储区域代号  z0:华东, z1:华北, z2:华南, na0:北美"
region = 'z0'

ret, info = bucket.mkbucketv2(bucket_name, region)
print(info)
print(ret)
assert info.status_code == 200
