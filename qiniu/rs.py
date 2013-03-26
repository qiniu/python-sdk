# -*- coding: utf-8 -*-
import auth_digest
import config
from base64 import urlsafe_b64encode

class Rs(object):
	conn = None
	def __init__(self, conn=None):
		if conn is None:
			conn = auth_digest.Client()
		self.conn = conn
	
	def stat(self, bucket, key):
		return self.conn.call(uri_stat(bucket, key))

	def delete(self, bucket, key):
		return self.conn.call(uri_delete(bucket, key))

	def move(self, bucket_src, key_src, bucket_dest, key_dest):
		return self.conn.call(uri_move(bucket_src, key_src, bucket_dest, key_dest))

	def copy(self, bucket_src, key_src, bucket_dest, key_dest):
		return self.conn.call(uri_copy(bucket_src, key_src, bucket_dest, key_dest))

	def batch(self, ops):
		return self.conn.call_with_form("/batch", dict(op=ops))

	def batch_stat(self, entries):
		ops = []
		for entry in entries:
			ops.append(uri_stat(entry.bucket, entry.key))
		return self.batch(ops)

	def batch_delete(self, entries):
		ops = []
		for entry in entries:
			ops.append(uri_delete(entry.bucket, entry.key))
		return self.batch(ops)

	def batch_move(self, entryies):
		ops = []
		for entry in entries:
			ops.append(uri_move(entry.bucket, entry.key))
		return self.batch(ops)

	def batch_copy(self, entryies):
		ops = []
		for entry in entries:
			ops.append(uri_copy(entry.bucket, entry.key))
		return self.batch(ops)

class EntryPath(object):
	bucket = None
	key = None
	def __init__(self, bucket, key):
		self.bucket = bucket
		self.key = key

class EntryPathPair:
	src = None
	dest = None
	def __init__(self, src, dest):
		self.src = src
		self.dest = dest

def uri_stat(bucket, key):
	return "/stat/%s" % urlsafe_b64encode("%s:%s" % (bucket, key))

def uri_delete(bucket, key):
	return "/delete/%s" % urlsafe_b64encode("%s:%s" % (bucket, key))

def uri_move(bucket_src, key_src, bucket_dest, key_dest):
	src = urlsafe_b64encode("%s:%s" % (bucket_src, key_src))
	dest = urlsafe_b64encode("%s:%s" % (bucket_dest, key_dest))
	return "/move/%s/%s" % (src, dest)

def uri_copy(bucket_src, key_src, bucket_dest, key_dest):
	src = urlsafe_b64encode("%s:%s" % (bucket_src, key_src))
	dest = urlsafe_b64encode("%s:%s" % (bucket_dest, key_dest))
	return "/copy/%s/%s" % (src, dest)

if __name__ == "__main__":
	config.ACCESS_KEY = "tGf47MBl1LyT9uaNv-NZV4XZe7sKxOIa9RE2Lp8B"
	config.SECRET_KEY = "zhbiA6gcQMEi22uZ8CBGvmbnD2sR8SO-5S8qlLCG"
	rs = Rs()
	entries = [
		EntryPath("a", "ffdfd_9"),
		EntryPath("a", "hello_jpg"),
	]
	ret, err = rs.batch_stat(entries)
	if not err is None:
		print 'error:', err
		exit()
	print ret
