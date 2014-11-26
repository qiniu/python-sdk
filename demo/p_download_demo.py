# -*- coding: utf-8 -*-
# flake8: noqa
import os
import requests

from qiniu import Auth
from qiniu.compat import is_py2

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')

q = Auth(access_key, secret_key)

bucket = 'private-res'
key = 'gogopher.jpg'
base_url = 'http://%s/%s' % (bucket + '.qiniudn.com', key)
private_url = q.private_download_url(base_url, expires=3600)
print(private_url)
r = requests.get(private_url)
assert r.status_code == 200