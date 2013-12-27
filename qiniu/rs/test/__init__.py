# -*- coding: utf-8 -*-
import os
from urllib.request import urlopen

import qiniu.io
import qiniu.rs
import qiniu.conf

pic = "http://cheneya.qiniudn.com/hello_jpg"
key = 'QINIU_UNIT_TEST_PIC'


def setUp():
    qiniu.conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
    qiniu.conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
    bucket_name = os.getenv("QINIU_TEST_BUCKET")

    policy = qiniu.rs.PutPolicy(bucket_name)
    uptoken = policy.token()

    f = urlopen(pic)
    _, err = qiniu.io.put(uptoken, key, f)
    f.close()
    if err is None or err.startswith('file exists'):
        print(err)
        assert err is None or err.startswith('file exists')
    print(err)
