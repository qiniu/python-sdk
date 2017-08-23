# -*- coding: utf-8 -*-
"""
批量删除文件

https://developer.qiniu.com/kodo/api/1250/batch
"""


from qiniu import build_batch_delete, Auth, BucketManager

access_key = ''

secret_key = ''

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

bucket_name = ''

keys = ['1.gif', '2.txt', '3.png', '4.html']

ops = build_batch_delete(bucket_name, keys)
ret, info = bucket.batch(ops)
print(info)
