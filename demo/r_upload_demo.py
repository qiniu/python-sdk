# -*- coding: utf-8 -*-
# flake8: noqa
import os
import tempfile

from qiniu import Auth
from qiniu import put_file
from qiniu.compat import is_py2, b

import qiniu.config

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')

def create_temp_file(size):
    t = tempfile.mktemp()
    f = open(t, 'wb')
    f.seek(size-1)
    f.write(b('0'))
    f.close()
    return t

def remove_temp_file(file):
    try:
        os.remove(file)
    except OSError:
        pass

q = Auth(access_key, secret_key)

mime_type = "text/plain"
params = {'x:a': 'a'}

key = 'big'
token = q.upload_token(bucket_name, key)
localfile = create_temp_file(4 * 1024 * 1024 + 1)
progress_handler = lambda progress, total: progress
qiniu.set_default(default_up_host='a')
ret, info = put_file(token, key, localfile, params, mime_type, progress_handler=progress_handler)
print(info)
assert ret['key'] == key
qiniu.set_default(default_up_host=qiniu.config.UPAUTO_HOST)
remove_temp_file(localfile)