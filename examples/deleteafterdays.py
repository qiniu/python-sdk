# -*- coding: utf-8 -*-
# flake8: noqa

from qiniu import Auth
from qiniu import BucketManager

access_key = 'l6LRg3So-l_th3Ti5744bRyhp6O6kUACAep-KjEm'
secret_key = 'piOuakNoSNX0fdbggkQ4Rq2-bldLq3R90AB2LECc'

bucket_name = 'bernie'

q = Auth(access_key, secret_key)

bucket = BucketManager(q)

key = '2.mp4'

ret, info = bucket.delete_after_days(bucket_name, key, '5')
print(info)


