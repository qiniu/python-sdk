# -*- coding: utf-8 -*-
from StringIO import StringIO
from base64 import urlsafe_b64encode

import config
import auth_up
import auth_token

class PutAction(object):
	_entryURI = None
	mimeType = None
	customMeta = None
	crc32 = None
	rotate = None
	def __init__(self, bucket, key):
		self._entryURI = urlsafe_b64encode("%s:%s" % (bucket, key))

	def to_uri(self):
		buf = StringIO()
		buf.write(self._entryURI)

		if self.mimeType is not None:
			buf.write("/mimeType/%s" % urlsafe_b64encode(self.mimeType))

		if self.customMeta is not None:
			buf.write("/customMeta/%s" % urlsafe_b64encode(self.customMeta))

		if self.crc32 is not None:
			buf.write("/crc32/%s" % self.crc32)

		if self.rotate is not None:
			buf.write("/rotate/%s" % self.rotate)

		val = buf.getvalue()
		buf.close()
		return '/rs-put/%s/' % val

class Up(object):
	conn = None
	def __init__(self, token, host=None, conn=None):
		up_token = None

		if conn is None:
			conn = auth_up.Client(token, host=host)
		self.conn = conn
		self.up_token = token

	def put(self, filename, action, params, data):
		fields = [
			("action", action.to_uri()),
			("auth", self.up_token),
		]
		if params is not None:
			fields.append(("params", params))

		files = [
			("file", filename, action.mimeType, data)
		]
		return self.conn.call_with_multipart("/upload", fields, files)

	def put_file(self, filepath, action, params):
		f = open(filepath)
		data = f.read()
		f.close()
		filename = filepath[filepath.rfind('/')+1: ]
		return self.put(filename, action, params, data)
