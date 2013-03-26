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
		content_type, body = self.encode_multipart_formdata(fields, files)
		self.set_header("Content-Type", content_type)
		self.set_header("Content-Length", len(body))
		return self.call_with(path, body)

	def call_with_form(self, path, ops):
		self.set_header("Content-Type", "application/x-www-form-urlencoded")
		body = []
		for i in ops:
			if isinstance(ops[i], (list, tuple)):
				data = ('&%s=' % i).join(ops[i])
			else:
				data = ops[i]
			
			body.append('%s=%s' % (i, data))
		return self.call_with(path, '&'.join(body))

	def set_header(self, field, value):
		self._header[field] = value

	def set_headers(self, headers):
		self._header.update(headers)

	def encode_multipart_formdata(self, fields, files):
		"""
		 *  fields => [(key, value)]
		 *  files => [(key, filename, mimeType, value)]
		 *  return content_type, body
		"""
		BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
		CRLF = '\r\n'
		L = []
		for (key, value) in fields:
			L.append('--' + BOUNDARY)
			L.append('Content-Disposition: form-data; name="%s"' % key)
			L.append('')
			L.append(value)
		for (key, filename, mimeType, value) in files:
			L.append('--' + BOUNDARY)
			L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
			L.append('Content-Type: %s' % mimeType)
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

if __name__ == "__main__":
	ACCESS_KEY = "tGf47MBl1LyT9uaNv-NZV4XZe7sKxOIa9RE2Lp8B"
	SECRET_KEY = "zhbiA6gcQMEi22uZ8CBGvmbnD2sR8SO-5S8qlLCG"
	a = dict(a="b")
	print sign_json(ACCESS_KEY, SECRET_KEY, a)
	help(Client)
	
