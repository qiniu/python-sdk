# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode

from ..auth import digest
from .. import conf

_uri_op = lambda bucket, key: urlsafe_b64encode("%s:%s" % (bucket, key))

def uri_stat(bucket, key):
	return "/stat/%s" % _uri_op(bucket, key)

def uri_delete(bucket, key):
	return "/delete/%s" % _uri_op(bucket, key)

def uri_move(bucket_src, key_src, bucket_dest, key_dest):
	return "/move/%s/%s" % (_uri_op(bucket_src, key_src),
                                _uri_op(bucket_dest, key_dest))

def uri_copy(bucket_src, key_src, bucket_dest, key_dest):
        return "/copy/%s/%s" % (_uri_op(bucket_src, key_src),
                                _uri_op(bucket_dest, key_dest))


class Client(object):
	conn = None
	def __init__(self, mac=None):
		if mac is None:
			mac = digest.Mac()
		self.conn = digest.Client(host=conf.RS_HOST, mac=mac)

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

	def batch_stat(self, entries, batch_type=uri_stat):
		ops = []
		for entry in entries:
			ops.append(batch_type(entry.bucket, entry.key))
		return self.batch(ops)

	def batch_delete(self, entries):
		return self.batch_stat(entries, uri_delete)

	def batch_move(self, entries, batch_type=uri_move):
		ops = []
		for entry in entries:
			ops.append(batch_type(entry.src.bucket, entry.src.key, 
				entry.dest.bucket, entry.dest.key))
		return self.batch(ops)

	def batch_copy(self, entries):
		return self.batch_move(entries, uri_copy)

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
