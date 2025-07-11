# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth, put_file_v2
from qiniu import Zone, set_default

# 需要填写你的 Access Key 和 Secret Key
access_key = ''
secret_key = ''

# 构建鉴权对象
q = Auth(access_key, secret_key)

# 要上传的空间
bucket_name = 'bucket_name'

# 上传到七牛后保存的文件名
key = 'a.jpg'

# 生成上传 Token，可以指定过期时间等
token = q.upload_token(bucket_name, key, 3600)

# 要上传文件的本地路径
localfile = '/Users/abc/Documents/a.jpg'

# 指定固定域名的zone,不同区域uphost域名见下文档
# https://developer.qiniu.com/kodo/manual/1671/region-endpoint
# 未指定或上传错误，sdk会根据token自动查询对应的上传域名
# *.qiniup.com 支持https上传
# 备用*.qiniu.com域名 不支持https上传
# 要求https上传时，如果客户指定的两个host都错误，且sdk自动查询的第一个*.qiniup.com上传域名因意外不可用导致访问到备用*.qiniu.com会报ssl错误
# 建议https上传时查看上面文档，指定正确的host

zone = Zone(
    up_host='https://up.qiniup.com',
    up_host_backup='https://upload.qiniup.com',
    io_host='http://iovip.qbox.me',
    scheme='https')
set_default(default_zone=zone)

ret, info = put_file_v2(token, key, localfile)
print(info)
