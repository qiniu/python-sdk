# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

access_key = ''
secret_key = ''

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

bucket_name = ''

key = 'example.png'

mime_type = 'image/jpeg'

ret, info = bucket.change_mime(bucket_name, key, mime_type)
print(info)
