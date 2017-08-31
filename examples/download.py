# -*- coding: utf-8 -*-
# flake8: noqa

import requests
from qiniu import Auth

access_key = '...'
secret_key = '...'

q = Auth(access_key, secret_key)
bucket_domain = "..."
key = "..."

# 有两种方式构造base_url的形式
base_url = 'http://%s/%s' % (bucket_domain, key)

# 或者直接输入url的方式下载
# base_url = 'http://domain/key'

# 可以设置token过期时间
private_url = q.private_download_url(base_url, expires=3600)

print(private_url)
r = requests.get(private_url)
assert r.status_code == 200
