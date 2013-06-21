# -*- coding: utf-8 -*-
import unittest
import os
import random
import string

import rs
import config

def r(length):
	lib = string.ascii_uppercase
	return ''.join([random.choice(lib) for i in range(0, length)])

config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
key = "aa"
bucket_name = "a"
noexist_key = "noexist_key"
key2 = "rs_demo_test_key_1_" + r(5)
key3 = "rs_demo_test_key_2_" + r(5)
key4 = "rs_demo_test_key_3_" + r(5)

class TestRs(unittest.TestCase):
	def test_stat(self):
		r = rs.Rs()
		ret, err = r.stat(bucket_name, key)
		assert err is None
		assert ret is not None
		
		# error
		_, err = r.stat(bucket_name, noexist_key)
		assert err is not None
	
	def test_delete_move_copy(self):
		r = rs.Rs()
		r.delete(bucket_name, key2)
		r.delete(bucket_name, key3)
		
		ret, err = r.copy(bucket_name, key, bucket_name, key2)
		assert err is None, err
		
		ret, err = r.move(bucket_name, key2, bucket_name, key3)
		assert err is None, err
		
		ret, err = r.delete(bucket_name, key3)
		assert err is None, err
		
		# error
		_, err = r.delete(bucket_name, key2)
		assert err is not None
		
		_, err = r.delete(bucket_name, key3)
		assert err is not None

	def test_batch_stat(self):
		r = rs.Rs()
		entries = [
			rs.EntryPath(bucket_name, key),
			rs.EntryPath(bucket_name, key2),
		]
		ret, err = r.batch_stat(entries)
		assert err is None
		self.assertEqual(ret[0]["code"], 200)
		self.assertEqual(ret[1]["code"], 612)

	def test_batch_delete_move_copy(self):
		r = rs.Rs()
		e1 = rs.EntryPath(bucket_name, key)
		e2 = rs.EntryPath(bucket_name, key2)
		e3 = rs.EntryPath(bucket_name, key3)
		e4 = rs.EntryPath(bucket_name, key4)
		r.batch_delete([e2, e3, e4])
		
		# copy
		entries = [
			rs.EntryPathPair(e1, e2),
			rs.EntryPathPair(e1, e3),
		]
		ret, err = r.batch_copy(entries)
		assert err is None
		self.assertEqual(ret[0]["code"], 200)
		self.assertEqual(ret[1]["code"], 200)
		
		ret, err = r.batch_move([rs.EntryPathPair(e2, e4)])
		assert err is None
		self.assertEqual(ret[0]["code"], 200)
		
		ret, err = r.batch_delete([e3, e4])
		assert err is None
		self.assertEqual(ret[0]["code"], 200)
		
		r.batch_delete([e2, e3, e4])

if __name__ == "__main__":
	unittest.main()
