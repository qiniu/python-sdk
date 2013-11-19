# -*- coding: utf-8 -*-
import unittest
from qiniu import rsf
from qiniu import conf

import os
conf.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
conf.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
bucket_name = os.getenv("QINIU_TEST_BUCKET")


class TestRsf(unittest.TestCase):

    def test_list_prefix(self):
        c = rsf.Client()
        ret, err = c.list_prefix(bucket_name, limit=1)
        self.assertEqual(err is rsf.EOF or err is None, True)
        assert len(ret.get('items')) == 1


if __name__ == "__main__":
    unittest.main()
