# -*- coding: utf-8 -*-
import unittest
import os

import rs
import config

config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
pic = os.getenv("QINIU_TEST_PIC_1")
key = os.getenv("QINIU_PIC_KEY")
bucket_name = os.getenv("QINIU_BUCKET_NAME")
noexist_key = os.getenv("QINIU_NOEXIST_PIC_KEY")
key2 = "rs_demo_test_key"
key3 = "rs_demo_test_key_2"
key4 = "rs_demo_test_key_3"

r = rs.Rs()

class TestRs(unittest.TestCase):
	def test_stat(self):
		ret, err = r.stat(bucket_name, key)
		self.assertIsNone(err)
		self.assertIsNotNone(ret)
		
		# error
		_, err = r.stat(bucket_name, noexist_key)
		self.assertIsNotNone(err)
	
	def test_delete_move_copy(self):
		ret, err = r.copy(bucket_name, key, bucket_name, key2)
		self.assertIsNone(err)
		
		ret, err = r.move(bucket_name, key2, bucket_name, key3)
		self.assertIsNone(err)
		
		ret, err = r.delete(bucket_name, key3)
		self.assertIsNone(err)
		
		# error
		_, err = r.delete(bucket_name, key2)
		self.assertIsNotNone(err)
		
		_, err = r.delete(bucket_name, key3)
		self.assertIsNotNone(err)

	def test_batch_stat(self):
		entries = [
			rs.EntryPath(bucket_name, key),
			rs.EntryPath(bucket_name, key2),
		]
		ret, err = r.batch_stat(entries)
		self.assertIsNone(err)
		self.assertEqual(ret[0]["code"], 200)
		self.assertEqual(ret[1]["code"], 612)

	def test_batch_delete_move_copy(self):
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
		self.assertIsNone(err)
		self.assertEqual(ret[0]["code"], 200)
		self.assertEqual(ret[1]["code"], 200)
		
		ret, err = r.batch_move([rs.EntryPathPair(e2, e4)])
		self.assertIsNone(err)
		self.assertEqual(ret[0]["code"], 200)
		
		ret, err = r.batch_delete([e3, e4])
		self.assertIsNone(err)
		self.assertEqual(ret[0]["code"], 200)
		

if __name__ == "__main__":
	unittest.main()
