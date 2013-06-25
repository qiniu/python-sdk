# -*- coding: utf-8 -*-
import unittest
import config
import os
import json
from base64 import urlsafe_b64decode as decode
from base64 import urlsafe_b64encode as encode
from hashlib import sha1
import hmac

import rpc
import auth_token

config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_BUCKET_NAME")


class TestToken(unittest.TestCase):

    def test_put_policy(self):
        policy = auth_token.PutPolicy(bucket_name)
        policy.customer = "hello!"
        tokens = policy.token().split(':')
        self.assertEqual(config.ACCESS_KEY, tokens[0])
        data = json.loads(decode(tokens[2]))
        self.assertEqual(data["scope"], bucket_name)
        self.assertEqual(data["customer"], policy.customer)

        new_hmac = encode(
            hmac.new(config.SECRET_KEY, tokens[2], sha1).digest())
        self.assertEqual(new_hmac, tokens[1])

    def test_get_policy(self):
        policy = auth_token.GetPolicy(bucket_name)
        tokens = policy.token().split(':')
        data = json.loads(decode(tokens[2]))
        self.assertEqual(data["S"], bucket_name)

if __name__ == "__main__":
    unittest.main()
