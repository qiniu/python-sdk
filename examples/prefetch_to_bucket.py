# -*- coding: utf-8 -*-
# flake8: noqa

"""
拉取镜像源资源到空间

https://developer.qiniu.com/kodo/api/1293/prefetch
"""

from qiniu import Auth
from qiniu import BucketManager

access_key = '...'
secret_key = '...'


bucket_name = 'Bucket_Name'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

# 要拉取的文件名
key = 'test.jpg'

ret, info = bucket.prefetch(bucket_name, key)
print(info)
assert ret['key'] == key
