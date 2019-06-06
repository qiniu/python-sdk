# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth, put_file, etag, urlsafe_base64_encode
import qiniu.config
from qiniu import Zone, set_default

# 需要填写你的 Access Key 和 Secret Key
access_key = '...'
secret_key = '...'

# 构建鉴权对象
q = Auth(access_key, secret_key)

# 要上传的空间
bucket_name = 'Bucket_Name'

# 上传到七牛后保存的文件名
key = 'my-python-logo.png'

# 生成上传 Token，可以指定过期时间等
token = q.upload_token(bucket_name, key, 3600)

# 要上传文件的本地路径
localfile = 'stat.py'

# up_host, 指定上传域名，注意不同区域的qvm上传域名不同
# https://developer.qiniu.com/qvm/manual/4269/qvm-kodo

zone = Zone(
    up_host='free-qvm-z1-zz.qiniup.com',
    up_host_backup='free-qvm-z1-zz.qiniup.com',
    io_host='iovip.qbox.me',
    scheme='http')
set_default(default_zone=zone)

ret, info = put_file(token, key, localfile)
print(info)
assert ret['key'] == key
assert ret['hash'] == etag(localfile)
