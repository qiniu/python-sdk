# -*- coding: utf-8 -*-
# flake8: noqa

"""
批量解冻文件
https://developer.qiniu.com/kodo/api/1250/batch
"""

from qiniu import build_batch_restoreAr, Auth, BucketManager

# 七牛账号的公钥和私钥
access_key = '<access_key>'
secret_key = '<secret_key>'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

# 存储空间
bucket_name = "空间名"

# 字典的键为需要解冻的文件，值为解冻有效期1-7
ops = build_batch_restoreAr(bucket_name,
                            {"test00.png": 1,
                             "test01.jpeg": 2,
                             "test02.mp4": 3
                             }
                            )

ret, info = bucket.batch(ops)
print(info)
