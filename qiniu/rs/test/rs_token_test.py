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
        policy.returnUrl = "http://localhost:1234/path?query=hello"
        policy.returnBody = "$(sha1)"
        # Do not specify the returnUrl and callbackUrl at the same time
        policy.callbackUrl = "http://1.2.3.4/callback"
        policy.callbackBody = "$(bucket)"

        policy.saveKey = "$(sha1)"
        policy.insertOnly = 1
        policy.detectMime = 1
        policy.fsizeLimit = 1024
        policy.persistentNotifyUrl = "http://4.3.2.1/persistentNotifyUrl"
        policy.persistentOps = "avthumb/flash"

        tokens = policy.token().split(':')

        # chcek first part of token
        self.assertEqual(conf.ACCESS_KEY, tokens[0])
        data = json.loads(decode(tokens[2]))

        # check if same
        self.assertEqual(data["scope"], bucket_name)
        self.assertEqual(data["endUser"], policy.endUser)
        self.assertEqual(data["returnUrl"], policy.returnUrl)
        self.assertEqual(data["returnBody"], policy.returnBody)
        self.assertEqual(data["callbackUrl"], policy.callbackUrl)
        self.assertEqual(data["callbackBody"], policy.callbackBody)
        self.assertEqual(data["saveKey"], policy.saveKey)
        self.assertEqual(data["exclusive"], policy.insertOnly)
        self.assertEqual(data["detectMime"], policy.detectMime)
        self.assertEqual(data["fsizeLimit"], policy.fsizeLimit)
        self.assertEqual(
            data["persistentNotifyUrl"], policy.persistentNotifyUrl)
        self.assertEqual(data["persistentOps"], policy.persistentOps)

        new_hmac = encode(hmac.new(conf.SECRET_KEY, tokens[2], sha1).digest())
        self.assertEqual(new_hmac, tokens[1])

    def test_get_policy(self):
        base_url = rs.make_base_url(domain, key)
        policy = rs.GetPolicy()
        private_url = policy.make_request(base_url)

        f = urllib.urlopen(private_url)
        body = f.read()
        f.close()
        self.assertEqual(len(body) > 100, True)


class Test_make_base_url(unittest.TestCase):

    def test_unicode(self):
        url1 = rs.make_base_url('1.com', '你好')
        url2 = rs.make_base_url('1.com', u'你好')
        assert url1 == url2

if __name__ == "__main__":
    unittest.main()
