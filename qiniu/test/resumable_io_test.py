# -*- coding: utf-8 -*-
import os
import unittest
import string
import random
import platform
try:
    import zlib
    binascii = zlib
except ImportError:
    zlib = None
    import binascii
import urllib
import shutil
import StringIO
from tempfile import mktemp

from qiniu import conf
from qiniu.auth import up
from qiniu import resumable_io
from qiniu import rs

bucket = os.getenv("QINIU_TEST_BUCKET")
conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
test_env = os.getenv("QINIU_TEST_ENV")
is_travis = test_env == "travis"


def r(length):
    lib = string.ascii_uppercase
    return ''.join([random.choice(lib) for _ in range(0, length)])


class TestBlock(unittest.TestCase):

    def test_block(self):
        if is_travis:
            return
        host = conf.UP_HOST
        policy = rs.PutPolicy(bucket)
        uptoken = policy.token()
        client = up.Client(uptoken)

        # rets = [0, 0]
        data_slice_2 = "\nbye!"
        ret, err, code = resumable_io.mkblock(
            client, len(data_slice_2), data_slice_2, host)
        assert err is None, err
        self.assertEqual(ret["crc32"], binascii.crc32(data_slice_2))

        extra = resumable_io.PutExtra(bucket)
        extra.mimetype = "text/plain"
        extra.progresses = [ret]
        lens = 0
        for i in xrange(0, len(extra.progresses)):
            lens += extra.progresses[i]["offset"]

        key = u"sdk_py_resumable_block_4_%s" % r(9)
        ret, err, code = resumable_io.mkfile(client, key, lens, extra, host)
        assert err is None
        self.assertEqual(
            ret["hash"], "FtCFo0mQugW98uaPYgr54Vb1QsO0", "hash not match")
        rs.Client().delete(bucket, key)

    def test_put(self):
        if is_travis:
            return
        src = urllib.urlopen("http://pythonsdk.qiniudn.com/hello.jpg")
        ostype = platform.system()
        if ostype.lower().find("windows") != -1:
            tmpf = "".join([os.getcwd(), mktemp()])
        else:
            tmpf = mktemp()
        dst = open(tmpf, 'wb')
        shutil.copyfileobj(src, dst)
        src.close()

        policy = rs.PutPolicy(bucket)
        extra = resumable_io.PutExtra(bucket)
        extra.bucket = bucket
        extra.params = {"x:foo": "test"}
        key = "sdk_py_resumable_block_5_%s" % r(9)
        localfile = dst.name
        ret, err = resumable_io.put_file(policy.token(), key, localfile, extra)
        dst.close()
        os.remove(tmpf)
        assert err is None
        assert ret.get("x:foo") == "test", "return data not contains 'x:foo'"
        self.assertEqual(
            ret["hash"], "FnyTMUqPNRTdk1Wou7oLqDHkBm_p", "hash not match")
        rs.Client().delete(bucket, key)

    def test_put_4m(self):
        if is_travis:
            return
        ostype = platform.system()
        if ostype.lower().find("windows") != -1:
            tmpf = "".join([os.getcwd(), mktemp()])
        else:
            tmpf = mktemp()
        dst = open(tmpf, 'wb')
        dst.write("abcd" * 1024 * 1024)
        dst.flush()

        policy = rs.PutPolicy(bucket)
        extra = resumable_io.PutExtra(bucket)
        extra.bucket = bucket
        extra.params = {"x:foo": "test"}
        key = "sdk_py_resumable_block_6_%s" % r(9)
        localfile = dst.name
        ret, err = resumable_io.put_file(policy.token(), key, localfile, extra)
        dst.close()
        os.remove(tmpf)
        print err
        assert err is None, err
        assert ret.get("x:foo") == "test", "return data not contains 'x:foo'"
        self.assertEqual(
            ret["hash"], "FnIVmMd_oaUV3MLDM6F9in4RMz2U", "hash not match")
        rs.Client().delete(bucket, key)

    def test_put_0(self):
        if is_travis:
            return

        f = StringIO.StringIO('')

        policy = rs.PutPolicy(bucket)
        extra = resumable_io.PutExtra(bucket)
        extra.bucket = bucket
        extra.params = {"x:foo": "test"}
        key = "sdk_py_resumable_block_7_%s" % r(9)
        ret, err = resumable_io.put(policy.token(), key, f, 0, extra)

        assert err is None, err
        assert ret.get("x:foo") == "test", "return data not contains 'x:foo'"
        self.assertEqual(
            ret["hash"], "Fg==", "hash not match")
        rs.Client().delete(bucket, key)


if __name__ == "__main__":
    if not is_travis:
        unittest.main()
