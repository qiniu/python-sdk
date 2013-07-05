# -*- coding: utf-8 -*-
import StringIO
import unittest

from qiniu import rpc
from qiniu import conf

def round_tripper(client, method, path, body):
	pass

class ClsTestClient(rpc.Client):
	def round_tripper(self, method, path, body):
		round_tripper(self, method, path, body)
		return super(ClsTestClient, self).round_tripper(method, path, body)

client = ClsTestClient(conf.RS_HOST)

class TestClient(unittest.TestCase):
	def test_call(self):
		global round_tripper

		def tripper(client, method, path, body):
			self.assertEqual(path, "/hello")
			assert body is None

		round_tripper = tripper
		client.call("/hello")

	def test_call_with(self):
		global round_tripper
		def tripper(client, method, path, body):
			self.assertEqual(body, "body")

		round_tripper = tripper
		client.call_with("/hello", "body")

	def test_call_with_multipart(self):
		global round_tripper
		def tripper(client, method, path, body):
			target_type = "multipart/form-data"
			self.assertTrue(client._header["Content-Type"].startswith(target_type))
			start_index = client._header["Content-Type"].find("boundary")
			boundary = client._header["Content-Type"][start_index + 9: ]
			dispostion = 'Content-Disposition: form-data; name="auth"'
			tpl = "--%s\r\n%s\r\n\r\n%s\r\n--%s--\r\n" % (boundary, dispostion,
					"auth_string", boundary)
			self.assertEqual(len(tpl), client._header["Content-Length"])
			self.assertEqual(len(tpl), body.length())

		round_tripper = tripper
		client.call_with_multipart("/hello", fields={"auth": "auth_string"})

	def test_call_with_form(self):
		global round_tripper
		def tripper(client, method, path, body):
			self.assertEqual(body, "action=a&op=a&op=b")
			target_type = "application/x-www-form-urlencoded"
			self.assertEqual(client._header["Content-Type"], target_type)
			self.assertEqual(client._header["Content-Length"], len(body))

		round_tripper = tripper
		client.call_with_form("/hello", dict(op=["a", "b"], action="a"))


class TestMultiReader(unittest.TestCase):
	def test_multi_reader1(self):
		a = StringIO.StringIO('你好')
		b = StringIO.StringIO('abcdefg')
		c = StringIO.StringIO(u'悲剧')
		mr = rpc.MultiReader([a, b, c])
		data = mr.read()
		assert data.index('悲剧') > data.index('abcdefg')

	def test_multi_reader2(self):
		a = StringIO.StringIO('你好')
		b = StringIO.StringIO('abcdefg')
		c = StringIO.StringIO(u'悲剧')
		mr = rpc.MultiReader([a, b, c])
		data = mr.read(8)
		assert len(data) is 8


def encode_multipart_formdata2(fields, files):
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


class TestEncodeMultipartFormdata(unittest.TestCase):
	def test_encode(self):
		fields = {'a': '1', 'b': '2'}
		files = [
			{
				'filename': 'key1',
				'data': 'data1',
				'mime_type': 'application/octet-stream',
			},
			{
				'filename': 'key2',
				'data': 'data2',
				'mime_type': 'application/octet-stream',
			}
		]
		content_type, mr = rpc.Client('localhost').encode_multipart_formdata(fields, files)
		t, b = encode_multipart_formdata2(
			[('a', '1'), ('b', '2')],
			[('file', 'key1', 'data1'), ('file', 'key2', 'data2')]
		)
		assert t == content_type
		assert len(b) == mr.length()

	def test_unicode(self):
		def test1():
			files = [{'filename': '你好', 'data': '你好', 'mime_type': ''}]
			_, body = rpc.Client('localhost').encode_multipart_formdata(None, files)
			return len(body.read())
		def test2():
			files = [{'filename': u'你好', 'data': '你好', 'mime_type': ''}]
			_, body = rpc.Client('localhost').encode_multipart_formdata(None, files)
			return len(body.read())
		def test3():
			files = [{'filename': '你好', 'data': u'你好', 'mime_type': ''}]
			_, body = rpc.Client('localhost').encode_multipart_formdata(None, files)
			return len(body.read())
		def test4():
			files = [{'filename': u'你好', 'data': u'你好', 'mime_type': ''}]
			_, body = rpc.Client('localhost').encode_multipart_formdata(None, files)
			return len(body.read())

		assert test1() == test2()
		assert test2() == test3()
		assert test3() == test4()


if __name__ == "__main__":
	unittest.main()
