# -*- coding: utf-8 -*-
# flake8: noqa
import os

from qiniu import Auth, PersistentFop, build_op, op_save
from qiniu.compat import is_py2

if is_py2:
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

access_key = os.getenv('QINIU_ACCESS_KEY')
secret_key = os.getenv('QINIU_SECRET_KEY')
bucket_name = os.getenv('QINIU_TEST_BUCKET')

q = Auth(access_key, secret_key)

pfop = PersistentFop(q, 'testres', 'sdktest')
op = op_save('avthumb/m3u8/segtime/10/vcodec/libx264/s/320x240', 'pythonsdk', 'pfoptest')
ops = []
ops.append(op)
ret, info = pfop.execute('sintel_trailer.mp4', ops, 1)
print(info)
assert ret['persistentId'] is not None