# -*- coding: utf-8 -*-
import qiniu
from qiniu import CdnManager


# 账户ak，sk
access_key = '...'
secret_key = '...'

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

# 需要刷新的目录链接
dirs = [
    'http://aaa.example.com/doc/img/',
    'http://bbb.example.com/doc/video/'
]


# 刷新链接
refresh_dir_result = cdn_manager.refresh_dirs(dirs)
