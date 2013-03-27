# -*- coding: utf-8 -*-
import httplib
import json
from hashlib import sha1
from base64 import urlsafe_b64encode
import hmac

class Client(object):
	_conn = None
	_header = None
	def __init__(self, host):
		self._conn = httplib.HTTPConnection(host)
		self._header = {}

	def round_tripper(self, method, path, body):
		self._conn.request(method, path, body, self._header)
		return self._conn.getresponse()

	def call(self, path):
		return self.call_with(path, None)

	def call_with(self, path, body):
		ret = None
		try:
			resp = self.round_tripper("POST", path, body)
			ret = resp.read()
			ret = json.loads(ret)
		except IOError, e:
			return None, e
		except ValueError:
			pass

		if resp.status / 100 != 2:
			err_msg = ret if "error" not in ret else ret["error"]
			return None, err_msg
		return ret, None

	def call_with_multipart(self, path, fields=None, files=None):
		"""
		 *  fields => [(key, value)]
		 *  files => [(key, filename, value)]
		"""
		content_type, body = self.encode_multipart_formdata(fields, files)
		self.set_header("Content-Type", content_type)
		self.set_header("Content-Length", len(body))
		return self.call_with(path, body)

	def call_with_form(self, path, ops):
		"""
		 * ops => {"key": value/list()}
		"""
		
		body = []
		for i in ops:
			if isinstance(ops[i], (list, tuple)):
				data = ('&%s=' % i).join(ops[i])
			else:
				data = ops[i]
			
			body.append('%s=%s' % (i, data))
		body = '&'.join(body)
		
		self.set_header("Content-Type", "application/x-www-form-urlencoded")
		self.set_header("Content-Length", len(body))
		return self.call_with(path, body)

	def set_header(self, field, value):
		self._header[field] = value

	def set_headers(self, headers):
		self._header.update(headers)

	def encode_multipart_formdata(self, fields, files):
		"""
		 *  fields => [(key, value)]
		 *  files => [(key, filename, value)]
		 *  return content_type, body
		"""
		if files is None:
			files = []
		if fields is None:
			fields = []

		BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
		CRLF = '\r\n'
		L = []
		for (key, value) in fields:
			L.append('--' + BOUNDARY)
			L.append('Content-Disposition: form-data; name="%s"' % key)
			L.append('')
			L.append(value)
		for (key, filename, value) in files:
			L.append('--' + BOUNDARY)
			disposition = "Content-Disposition: form-data;"
			L.append('%s name="%s"; filename="%s"' % (disposition, key, filename))
			L.append('Content-Type: application/octet-stream')
			L.append('')
			L.append(value)
		L.append('--' + BOUNDARY + '--')
		L.append('')
		body = CRLF.join(L)
		content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
		return content_type, body

def sign(secret, data):
	hashed = hmac.new(secret, data, sha1)
	return urlsafe_b64encode(hashed.digest())

def sign_json(access, secret, data):
	data = urlsafe_b64encode(json.dumps(data, separators=(',',':')))
	return '%s:%s:%s' % (access, sign(secret, data), data)
