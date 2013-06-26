# -*- coding: utf-8 -*-
import unittest
from qiniu import rsf
from qiniu import conf

import os
conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_BUCKET_NAME")

class TestRsf(unittest.TestCase):
	def test_list_prefix(self):
		c = rsf.Rsf()
		ret, err = c.list_prefix(bucket_name)
		assert err is None
		self.assertEqual(len(ret.get('items'))>0, True)


if __name__ == "__main__":
	unittest.main()
