# -*- coding: utf-8 -*-

"""
预取资源到cdn节点

https://developer.qiniu.com/fusion/api/1227/file-prefetching
"""


import qiniu
from qiniu import CdnManager


# 账户ak，sk
access_key = '...'
secret_key = '...'

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

# 需要刷新的文件链接
urls = [
    'http://aaa.example.com/doc/img/',
    'http://bbb.example.com/doc/video/'
]


# 刷新链接
refresh_dir_result = cdn_manager.prefetch_urls(urls)
