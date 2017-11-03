# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth, put_file, etag, urlsafe_base64_encode
import qiniu.config
from qiniu.compat import is_py2, is_py3

# 需要填写你的 Access Key 和 Secret Key
access_key = '...'
secret_key = '...'

# 构建鉴权对象
q = Auth(access_key, secret_key)

# 要上传的空间
bucket_name = 'if-bc'

# 上传到七牛后保存的文件名
key = 'my-python-七牛.png'

# 生成上传 Token，可以指定过期时间等
token = q.upload_token(bucket_name, key, 3600)

# 要上传文件的本地路径
localfile = '/Users/jemy/Documents/qiniu.png'

ret, info = put_file(token, key, localfile)
print(ret)
print(info)

if is_py2:
    assert ret['key'].encode('utf-8') == key
elif is_py3:
    assert ret['key'] == key

assert ret['hash'] == etag(localfile)
