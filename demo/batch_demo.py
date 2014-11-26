# -*- coding: utf-8 -*-
# flake8: noqa
import os

from qiniu import Auth
from qiniu import BucketManager, build_batch_rename
from qiniu.compat import is_py2

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')

q = Auth(access_key, secret_key)
bucket = BucketManager(q)

# batch stat
from qiniu import build_batch_stat

ops = build_batch_stat(bucket_name, ['python-sdk.html', 'python-sdk.html'])
ret, info = bucket.batch(ops)
print(info)
assert ret[0]['code'] == 200

# # batch copy
# from qiniu import build_batch_copy

# key = 'copyto'
# ops = build_batch_copy(bucket_name, {'copyfrom': key}, bucket_name)
# ret, info = bucket.batch(ops)
# print(info)
# assert ret[0]['code'] == 200

# # batch move
# from qiniu import build_batch_move

# key = 'moveto'
# key2 = key + 'move'
# ops = build_batch_move(bucket_name, {key: key2}, bucket_name)
# ret, info = bucket.batch(ops)
# print(info)
# assert ret[0]['code'] == 200

# batch delete
# from qiniu import build_batch_delete

# ops = build_batch_delete(bucket_name, ['python-sdk.html'])
# ret, info = self.bucket.batch(ops)
# print(info)
# assert ret[0]['code'] == 612