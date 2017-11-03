# -*- coding: utf-8 -*-
import qiniu
from qiniu import CdnManager

# 账户ak，sk
access_key = '...'
secret_key = '...'

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

# 需要刷新的文件链接
urls = [
    'http://aaa.example.com/a.gif',
    'http://bbb.example.com/b.jpg'
]

# 刷新链接
refresh_url_result = cdn_manager.refresh_urls(urls)
print(refresh_url_result)
