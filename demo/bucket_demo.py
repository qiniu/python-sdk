# -*- coding: utf-8 -*-
# flake8: noqa
import os

from qiniu import Auth
from qiniu import BucketManager
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


# stat
ret, info = bucket.stat(bucket_name, 'python-sdk.html')
print(info)
assert 'hash' in ret

# # copy
# key = 'copyto'
# ret, info = bucket.copy(bucket_name, 'copyfrom', bucket_name, key)
# print(info)
# assert ret == {}

# # move
# key = 'renameto'
# key2 = key + 'move'
# ret, info = bucket.move(bucket_name, key, bucket_name, key2)
# print(info)
# assert ret == {}

# # delete
# ret, info = bucket.delete(bucket_name, 'del')
# print(info)
# assert ret is None
# assert info.status_code == 612


# # prefetch

# ret, info = bucket.prefetch(bucket_name, 'python-sdk.html')
# print(info)
# assert ret == {}

# # fetch
# ret, info = bucket.fetch('http://developer.qiniu.com/docs/v6/sdk/python-sdk.html', bucket_name, 'fetch.html')
# print(info)
# assert ret == {}


# # list

# ret, eof, info = bucket.list(bucket_name, limit=4)
# print(info)
# assert eof is False
# assert len(ret.get('items')) == 4
# ret, eof, info = bucket.list(bucket_name, limit=100)
# print(info)
# assert eof is True

# # list all

# def list_all(bucket_name, bucket=None, prefix=None, limit=None):
# 	if bucket is None:
# 		bucket = BucketManager(q)
# 	marker = None
# 	eof = False
# 	while eof is False:
# 		ret, eof, info = bucket.list(bucket_name, prefix=prefix, marker=marker, limit=limit)
# 		marker = ret.get('marker', None)
# 		for item in ret['items']:
# 			print(item['key'])
# 			pass
# 	if eof is not True:
# 		# 错误处理
# 		pass

# list_all(bucket_name, bucket, 't', 10)