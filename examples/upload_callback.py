# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth, put_file, etag

access_key = '...'
secret_key = '...'

q = Auth(access_key, secret_key)

bucket_name = 'Bucket_Name'

key = 'my-python-logo.png'

#上传文件到七牛后， 七牛将文件名和文件大小回调给业务服务器。
policy = {
 'callbackUrl': 'http://your.domain.com/callback.php',
 'callbackBody': 'filename=$(fname)&filesize=$(fsize)'
 }

token = q.upload_token(bucket_name, key, 3600, policy)

localfile = './sync/bbb.jpg'

ret, info = put_file(token, key, localfile)
print(info)
assert ret['key'] == key
assert ret['hash'] == etag(localfile)

