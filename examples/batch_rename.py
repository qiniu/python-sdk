# -*- coding: utf-8 -*-
"""
批量重命名文件

https://developer.qiniu.com/kodo/api/1250/batch
"""


from qiniu import build_batch_rename, Auth, BucketManager

access_key = ''

secret_key = ''


q = Auth(access_key, secret_key)

bucket = BucketManager(q)

bucket_name = ''


# force为true时强制同名覆盖, 字典的键为原文件，值为目标文件
ops = build_batch_rename(bucket_name, {'src_key1': 'target_key1', 'src_key2': 'target_key2'}, force='true')
ret, info = bucket.batch(ops)
print(info)
