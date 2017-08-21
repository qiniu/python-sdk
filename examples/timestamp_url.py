# -*- coding: utf-8 -*-
import qiniu
from qiniu import CdnManager
from qiniu.services.cdn.manager import create_timestamp_anti_leech_url

host = 'http://ymhb.qiniuts.com'

encrypt_key = '5e99688aeab9329af09b2ba8388b87882ba811ba'

file_name = 'yum.png'

query_string_dict = {'imageInfo': ''}

deadline = 1503414248

p_url = create_timestamp_anti_leech_url(host, file_name, query_string_dict, encrypt_key, deadline)

print(p_url)
