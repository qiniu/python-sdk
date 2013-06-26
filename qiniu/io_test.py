# -*- coding: utf-8 -*-
import os
import unittest
import string
import random
import rs
import conf
import zlib
from base64 import urlsafe_b64encode as encode

import io

conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_BUCKET_NAME")

policy = rs.PutPolicy(bucket_name)
extra = io.PutExtra(bucket_name)
extra.mime_type = "text/plain"

def r(length):
	lib = string.ascii_uppercase
	return ''.join([random.choice(lib) for i in range(0, length)])

class TestUp(unittest.TestCase):
	def test(self):
		def test_put():
			key = "test_%s" % r(9)
			params = "op=3"
			data = "hello bubby!"
			extra.check_crc = 2
			extra.crc32 = zlib.crc32(data) & 0xFFFFFFFF
			ret, err = io.put(policy.token(), key, data, extra)
			assert err is None

		def test_put_same_crc():
			key = "test_%s" % r(9)
			params = "op=3"
			data = "hello bubby!"
			extra.check_crc = 2
			ret, err = io.put(policy.token(), key, data, extra)
			assert err is None

		test_put()
		test_put_same_crc()

	def test_put_file(self):
		localfile = "%s" % __file__
		key = "test_%s" % r(9)

		extra.check_crc = 1
		ret, err = io.put_file(policy.token(), key, localfile, extra)
		assert err is None
		assert ret is not None

	def test_put_crc_fail(self):
		key = "test_%s" % r(9)
		params = "op=3"
		data = "hello bubby!"
		extra.check_crc = 2
		extra.crc32 = "wrong crc32"
		ret, err = io.put(policy.token(), key, data, extra)
		assert err is not None


if __name__ == "__main__":
	unittest.main()
