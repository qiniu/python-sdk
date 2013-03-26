# -*- coding: utf-8 -*-
import os
import unittest
import string
import random
import auth_token
import config
from base64 import urlsafe_b64encode as encode

import up

config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
pic = os.getenv("QINIU_TEST_PIC_1")
noexist_pic = os.getenv("QINIU_NOEXIST_PIC")
bucket_name = os.getenv("QINIU_BUCKET_NAME")

policy = auth_token.PutPolicy(bucket_name)

def r(length):
	lib = string.ascii_uppercase
	return ''.join([random.choice(lib) for i in range(0, length)])

class TestPutAction(unittest.TestCase):
	def test(self):
		key = "test_%s" % r(9)
		action = up.PutAction(bucket_name, key)
		action.customMeta = "hehe"
		action.crc32 = 12324134
		action.rotate = 42
		action.mimeType = "text/plain"
		
		target = '/rs-put/%s/mimeType/%s/customMeta/%s/crc32/12324134/rotate/42/' % (
			encode('%s:%s' % (bucket_name, key)),
			encode(action.mimeType), encode(action.customMeta)
		)
		self.assertEqual(action.to_uri(), target)

class TestUp(unittest.TestCase):

	def test_put(self):
		u = up.Up(policy.token())
		filename = "start.txt"
		key = "test_%s" % r(9)
		action = up.PutAction(bucket_name, key)
		params = "op=3"
		data = "hello bubby!"
		ret, err = u.put(filename, action, params, data)
		assert err is None

	def test_put_file(self):
		u = up.Up(policy.token())

		filepath = "./%s" % __file__
		key = "test_%s" % r(9)
		action = up.PutAction(bucket_name, key)
		action.mimeType = "text/plain"
		params = "op=3"

		ret, err = u.put_file(filepath, action, params)
		assert err is None
		self.assertIsNotNone(ret)

if __name__ == "__main__":
	unittest.main()
