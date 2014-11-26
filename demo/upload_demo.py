# -*- coding: utf-8 -*-
# flake8: noqa
import os

from qiniu import Auth, etag
from qiniu import put_data, put_file
from qiniu.compat import is_py2

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')

q = Auth(access_key, secret_key)

# 上传流
key = 'a\\b\\c"你好'
data = 'hello bubby!'
token = q.upload_token(bucket_name)
ret, info = put_data(token, key, data)
print(info)
assert ret['key'] == key

key = ''
data = 'hello bubby!'
token = q.upload_token(bucket_name, key)
ret, info = put_data(token, key, data, check_crc=True)
print(info)
assert ret['key'] == key

# 上传文件
localfile = __file__
key = 'test_file'
mime_type = "text/plain"
params = {'x:a': 'a'}

token = q.upload_token(bucket_name, key)
ret, info = put_file(token, key, localfile, params=params, mime_type=mime_type, check_crc=True)
print(info)
assert ret['key'] == key
assert ret['hash'] == etag(localfile)