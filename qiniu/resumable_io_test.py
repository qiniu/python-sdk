# -*- coding: utf-8 -*-
import os
import config
import unittest
import zlib

import auth_token
import auth_up
import resumable_io
import rs

bucket = os.getenv("QINIU_BUCKET_NAME")
config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")

class TestBlock(unittest.TestCase):
	def test_block(self):
		policy = auth_token.PutPolicy(bucket)
		uptoken = policy.token()
		client = auth_up.Client(uptoken)

		rets = [0, 0]
		data_slice_2 = "\nbye!"
		ret, err = resumable_io.mkblock(client, len(data_slice_2), data_slice_2)
		assert err is None, err 
		self.assertEqual(ret["crc32"], zlib.crc32(data_slice_2))

		extra = resumable_io.PutExtra(bucket)
		extra.mimetype = "text/plain"
		extra.progresses = [ret]
		lens = 0
		for i in xrange(0, len(extra.progresses)):
			lens += extra.progresses[i]["offset"]

		key = "sdk_py_resumable_block_4"
		ret, err = resumable_io.mkfile(client, key, lens, extra)
		assert err is None, err
		self.assertEqual(ret["hash"], "FtCFo0mQugW98uaPYgr54Vb1QsO0", "hash not match")
		rs.Rs().delete(bucket, key)
	
	def test_put(self):
		policy = auth_token.PutPolicy(bucket)
		extra = resumable_io.PutExtra(bucket)
		extra.bucket = bucket
		key = "sdk_py_resumable_block_5"
		localfile = "../demo-pic.jpeg"
		ret, err = resumable_io.put_file(policy.token(), key, localfile, extra)
		assert err is None, err
		self.assertEqual(ret["hash"], "FuoNzfC-yMVcglmW8hAcilDaKh5C", "hash not match")
		rs.Rs().delete(bucket, key)
			

if __name__ == "__main__":
	unittest.main()
