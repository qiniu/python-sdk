# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager
from qiniu import build_batch_copy
from qiniu import build_batch_move,build_batch_rename

access_key = '...'
secret_key = '...'

# 初始化Auth状态
q = Auth(access_key, secret_key)

# 初始化BucketManager
bucket = BucketManager(q)
keys = {'123.jpg': '123.jpg'}

# ops = build_batch_copy( 'teest', keys, 'teest',force='true')
# ops = build_batch_move('teest', keys, 'teest', force='true')
ops = build_batch_rename('teest', keys, force='true')

ret, info = bucket.batch(ops)
print(ret)
print(info)
assert ret == {}
