# -*- coding: utf-8 -*-
# flake8: noqa
# import hashlib

from qiniu import Auth, put_file, urlsafe_base64_encode
import qiniu.config
from qiniu.compat import is_py2, is_py3

# 需要填写你的 Access Key 和 Secret Key
access_key = '...'
secret_key = '...'

# 构建鉴权对象
q = Auth(access_key, secret_key)

# 要上传的空间
bucket_name = ''

# 上传到七牛后保存的文件名
key = 'my-python-七牛.png'

# 生成上传 Token，可以指定过期时间等
token = q.upload_token(bucket_name, key, 3600)

# 要上传文件的本地路径
localfile = '/Users/jemy/Documents/qiniu.png'

# 上传时，sdk 会自动计算文件 hash 作为参数传递给服务端确保上传完整性
# （若不一致，服务端会拒绝完成上传）
# 但在访问文件时，服务端可能不会提供 MD5 或者编码格式不是期望的
# 因此若有需有，请通过元数据功能自定义 MD5 或其他 hash 字段
# hasher = hashlib.md5()
# with open(localfile, 'rb') as f:
#     for d in f:
#         hasher.update(d)
# object_metadata = {
#     'x-qn-meta-md5': hasher.hexdigest()
# }

ret, info = put_file(
    token,
    key,
    localfile
    # metadata=object_metadata
)
print(ret)
print(info)

if is_py2:
    assert ret['key'].encode('utf-8') == key
elif is_py3:
    assert ret['key'] == key
