# -*- coding: utf-8 -*-

"""
获取一个配置时间戳防盗链的url
"""

from qiniu.services.cdn.manager import create_timestamp_anti_leech_url
import time

host = 'http://a.example.com'

# 配置时间戳时指定的key
encrypt_key = ''

# 资源路径
file_name = 'a/b/c/example.jpeg'

# 查询字符串,不需加?
query_string = ''

# 截止日期的时间戳,秒为单位，3600为当前时间一小时之后过期
deadline = int(time.time())+3600


timestamp_url = create_timestamp_anti_leech_url(host, file_name, query_string, encrypt_key, deadline)

print(timestamp_url)
