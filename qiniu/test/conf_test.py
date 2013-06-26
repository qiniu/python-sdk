# -*- coding: utf-8 -*-
import unittest
from qiniu import conf

class TestConfig(unittest.TestCase):
	def test_USER_AGENT(self):
		assert len(conf.USER_AGENT) >= len('qiniu python-sdk')
	
if __name__ == '__main__':
	unittest.main()
