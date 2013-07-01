# -*- coding: utf-8 -*-
import os
import unittest
import string
import random
try:
	import zlib as binascii
except ImportError:
	import binascii
import urllib
import tempfile
import shutil

from qiniu import conf
from qiniu.auth import up
from qiniu import resumable_io
from qiniu import rs

bucket = os.getenv("QINIU_BUCKET_NAME")
conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")


def r(length):
	lib = string.ascii_uppercase
	return ''.join([random.choice(lib) for i in range(0, length)])

class TestBlock(unittest.TestCase):
	def test_block(self):
		policy = rs.PutPolicy(bucket)
		uptoken = policy.token()
		client = up.Client(uptoken)

		rets = [0, 0]
		data_slice_2 = "\nbye!"
		ret, err = resumable_io.mkblock(client, len(data_slice_2), data_slice_2)
		assert err is None, err 
		self.assertEqual(ret["crc32"], binascii.crc32(data_slice_2))

		extra = resumable_io.PutExtra(bucket)
		extra.mimetype = "text/plain"
		extra.progresses = [ret]
		lens = 0
		for i in xrange(0, len(extra.progresses)):
			lens += extra.progresses[i]["offset"]

		key = u"sdk_py_resumable_block_4_%s" % r(9)
		ret, err = resumable_io.mkfile(client, key, lens, extra)
		assert err is None, err
		self.assertEqual(ret["hash"], "FtCFo0mQugW98uaPYgr54Vb1QsO0", "hash not match")
		rs.Client().delete(bucket, key)
	
	def test_put(self):
		src = urllib.urlopen("http://cheneya.qiniudn.com/hello_jpg")
		dst = tempfile.NamedTemporaryFile()
		shutil.copyfileobj(src, dst)
		src.close()

		policy = rs.PutPolicy(bucket)
		extra = resumable_io.PutExtra(bucket)
		extra.bucket = bucket
		key = "sdk_py_resumable_block_5_%s" % r(9)
		localfile = dst.name
		ret, err = resumable_io.put_file(policy.token(), key, localfile, extra)
		dst.close()

		assert err is None, err
		self.assertEqual(ret["hash"], "FnyTMUqPNRTdk1Wou7oLqDHkBm_p", "hash not match")
		rs.Client().delete(bucket, key)
			

if __name__ == "__main__":
	unittest.main()
