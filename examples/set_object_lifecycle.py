# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

access_key = 'your_ak'
secret_key = 'your_sk'

# 初始化 Auth
q = Auth(access_key, secret_key)

# 初始化 BucketManager
bucket = BucketManager(q)

# 目标空间
bucket_name = 'your_bucket_name'
# 目标 key
key = 'path/to/key'

# bucket_name 更新 rule
ret, info = bucket.set_object_lifecycle(
    bucket=bucket_name,
    key=key,
    to_line_after_days=10,
    to_archive_after_days=20,
    to_deep_archive_after_days=30,
    delete_after_days=40,
    cond={
        'hash': 'object_hash'
    }
)
print(ret)
print(info)
