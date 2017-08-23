# -*- coding: utf-8 -*-
"""
查询指定域名指定时间段内的带宽
"""
import qiniu
from qiniu import CdnManager


# 账户ak，sk
access_key = ''
secret_key = ''

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

startDate = '2017-07-20'

endDate = '2017-08-20'

granularity = 'day'

urls = [
    'a.example.com',
    'b.example.com'
]

ret, info = cdn_manager.get_bandwidth_data(urls, startDate, endDate, granularity)

print(ret)
print(info)
