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

# 你要测试的空间， 并且这个key在你空间中存在
bucket_name = 'Bucket_Name'
key = 'python-logo.png'

# 将文件从文件key 移动到文件key2，可以实现文件的重命名 可以在不同bucket移动
key2 = 'python-logo2.png'

ret, info = bucket.move(bucket_name, key, bucket_name, key2)
print(info)
assert ret == {}
