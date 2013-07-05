# -*- coding: utf-8 -*-
import unittest
import os
import json
from base64 import urlsafe_b64decode as decode
from base64 import urlsafe_b64encode as encode
from hashlib import sha1
import hmac
import urllib

from qiniu import conf
from qiniu import rpc
from qiniu import rs

conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_TEST_BUCKET")
domain = os.getenv("QINIU_TEST_DOMAIN")
key = 'QINIU_UNIT_TEST_PIC'

class TestToken(unittest.TestCase):
	def test_put_policy(self):
		policy = rs.PutPolicy(bucket_name)
		policy.endUser = "hello!"
		tokens = policy.token().split(':')
		self.assertEqual(conf.ACCESS_KEY, tokens[0])
		data = json.loads(decode(tokens[2]))
		self.assertEqual(data["scope"], bucket_name)
		self.assertEqual(data["endUser"], policy.endUser)

		new_hmac = encode(hmac.new(conf.SECRET_KEY, tokens[2], sha1).digest())
		self.assertEqual(new_hmac, tokens[1])

	def test_get_policy(self):
		base_url = rs.make_base_url(domain, key)
		policy = rs.GetPolicy()
		private_url = policy.make_request(base_url)

		f = urllib.urlopen(private_url)
		body = f.read()
		f.close()
		self.assertEqual(len(body)>100, True)


if __name__ == "__main__":
	unittest.main()
