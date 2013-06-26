# -*- coding: utf-8 -*-
import unittest
import conf
import os
import json
from base64 import urlsafe_b64decode as decode
from base64 import urlsafe_b64encode as encode
from hashlib import sha1
import hmac
import urllib

import rpc
import auth_token

conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_BUCKET_NAME")
domain = os.getenv("QINIU_DOMAIN")
key = os.getenv("QINIU_PIC_KEY")

class TestToken(unittest.TestCase):
	def test_put_policy(self):
		policy = auth_token.PutPolicy(bucket_name)
		policy.endUser = "hello!"
		tokens = policy.token().split(':')
		self.assertEqual(conf.ACCESS_KEY, tokens[0])
		data = json.loads(decode(tokens[2]))
		self.assertEqual(data["scope"], bucket_name)
		self.assertEqual(data["endUser"], policy.endUser)

		new_hmac = encode(hmac.new(conf.SECRET_KEY, tokens[2], sha1).digest())
		self.assertEqual(new_hmac, tokens[1])

	def test_get_policy(self):
		base_url = auth_token.make_base_url(domain, key)
		policy = auth_token.GetPolicy()
		private_url = policy.make_request(base_url)

		f = urllib.urlopen(private_url)
		body = f.read()
		self.assertEqual(len(body)>100, True)


if __name__ == "__main__":
	unittest.main()
