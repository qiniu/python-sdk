# -*- coding: utf-8 -*-
import httplib
import json
import cStringIO
import conf


class Client(object):
	_conn = None
	_header = None

	def __init__(self, host):
		self._conn = httplib.HTTPConnection(host)
		self._header = {}

	def round_tripper(self, method, path, body):
		self._conn.request(method, path, body, self._header)
		resp = self._conn.getresponse()
		return resp

	def call(self, path):
		return self.call_with(path, None)

	def call_with(self, path, body, content_type=None, content_length=None):
		ret = None

		self.set_header("User-Agent", conf.USER_AGENT)
		if content_type is not None:
			self.set_header("Content-Type", content_type)

		if content_length is not None:
			self.set_header("Content-Length", content_length)

		resp = self.round_tripper("POST", path, body)
		try:
			ret = resp.read()
			ret = json.loads(ret)
		except IOError, e:
			return None, e
		except ValueError:
			pass

		if resp.status / 100 != 2:
			err_msg = ret if "error" not in ret else ret["error"]
			detail = resp.getheader("x-log", None)
			if detail is not None:
				err_msg += ", detail:%s" % detail

			return None, err_msg

		return ret, None

	def call_with_multipart(self, path, fields=None, files=None):
		"""
		 *  fields => {key}
		 *  files => [{filename, data, content_type}]
		"""
		content_type, body = self.encode_multipart_formdata(fields, files)
		return self.call_with(path, body, content_type, len(body))

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

		content_type = "application/x-www-form-urlencoded"
		return self.call_with(path, body, content_type, len(body))

	def set_header(self, field, value):
		self._header[field] = value

	def set_headers(self, headers):
		self._header.update(headers)

	def encode_multipart_formdata(self, fields, files):
		"""
		 *  fields => {key}
		 *  files => [{filename, data, content_type}]
		 *  return content_type, content_length, body
		"""
		if files is None:
			files = []
		if fields is None:
			fields = {}

		readers = []
		BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
		CRLF = '\r\n'
		L1 = []
		for key in fields:
			L1.append('--' + BOUNDARY)
			L1.append('Content-Disposition: form-data; name="%s"' % key)
			L1.append('')
			L1.append(fields[key])
		b1 = CRLF.join(L1)
		readers.append(b1)

		for file_info in files:
			L = []
			L.append('')
			L.append('--' + BOUNDARY)
			disposition = "Content-Disposition: form-data;"
			L.append('%s name="file"; filename="%s"' % (disposition, file_info.get('filename')))
			L.append('Content-Type: %s' % file_info.get('content_type', 'application/octet-stream'))
			L.append('')
			L.append('')
			b2 = CRLF.join(L)
			readers.append(b2)

			data = file_info.get('data')
			readers.append(data)

		L3 = ['', '--' + BOUNDARY + '--', '']
		b3 = CRLF.join(L3)
		readers.append(b3)

		content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
		return content_type, MultiReader(readers)


class MultiReader(object):
	""" class MultiReader([reader...])

	MultiReader returns a read()able object that's the logical concatenation of
	the provided input readers.  They're read sequentially.
	"""

	def __init__(self, readers):
		self.readers = []
		self.content_length = 0
		for r in readers:
			if hasattr(r, 'read'):
				self.content_length += self._get_content_length(r)
			else:
				buf = r
				if not isinstance(buf, basestring):
					buf = str(buf)
				buf = encode_unicode(buf)
				r = cStringIO.StringIO(buf)
				self.content_length += len(buf)
			self.readers.append(r)

	def __len__(self):
		return self.content_length

	def _get_content_length(self, reader):
		data_len = 0
		try:
			reader.seek(0, 2)
			data_len= reader.tell()
			reader.seek(0, 0)
		except (AttributeError, OSError):
			print 'can not get content_length'
		return data_len

	def read(self, n=-1):
		if n is None or n == -1:
			return ''.join([encode_unicode(r.read()) for r in self.readers])
		else:
			L = []
			while len(self.readers) > 0 and n > 0:
				b = self.readers[0].read(n)
				if len(b) == 0:
					self.readers = self.readers[1:]
				else:
					L.append(encode_unicode(b))
					n -= len(b)
			return ''.join(L)


def encode_unicode(u):
	if isinstance(u, unicode):
		u = u.encode('utf8')
	return u
