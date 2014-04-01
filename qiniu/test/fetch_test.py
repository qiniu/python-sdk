#coding:utf-8
import unittest
from qiniu import rs
from qiniu import conf
import os

bucket = os.getenv("QINIU_TEST_BUCKET")
conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
conf.RS_HOST = "iovip.qbox.me"

class TestFetch(unittest.TestCase):
    def test_fetch(self):
        key = "fetchtest.jpg"
        url = "http://cheneya.qiniudn.com/hello_jpg"
        ret, err = rs.Client().fetch(bucket, key, url)
        assert err is None, err

if __name__ == "__main__":
    unittest.main()
