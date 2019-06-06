# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth
from qiniu import BucketManager

access_key = '...'
secret_key = '...'

q = Auth(access_key, secret_key)
bucket = BucketManager(q)

bucket_name = 'Bucket_Name'
# 前缀
prefix = None
# 列举条目
limit = 10
# 列举出除'/'的所有文件以及以'/'为分隔的所有前缀
delimiter = None
# 标记
marker = None

ret, eof, info = bucket.list(bucket_name, prefix, marker, limit, delimiter)

print(info)

assert len(ret.get('items')) is not None
