# -*- coding: utf-8 -*-
import qiniu
from qiniu import CdnManager


# 账户ak，sk
access_key = ''
secret_key = ''

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

log_date = '2017-07-20'

urls = [
    'a.example.com',
    'b.example.com'
]

# 获得指定域名流量
ret, info = cdn_manager.get_log_list_data(urls, log_date)

print(ret)
print(info)
