# -*- coding: utf-8 -*-
import unittest

import auth
import config

def round_tripper(client, method, path, body):
	pass

class ClsTestClient(auth.Client):
	def round_tripper(self, method, path, body):
		round_tripper(self, method, path, body)
		return super(ClsTestClient, self).round_tripper(method, path, body)

client = ClsTestClient(config.RS_HOST)

class TestClient(unittest.TestCase):
	def test_call(self):
		global round_tripper
		
		def tripper(client, method, path, body):
			self.assertEqual(path, "/hello")
			assert err is None
		
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
			self.assertEqual(len(body), client._header["Content-Length"])
			target_type = "multipart/form-data"
			self.assertTrue(client._header["Content-Type"].startswith(target_type))
			start_index = client._header["Content-Type"].find("boundary")
			boundary = client._header["Content-Type"][start_index + 9: ]
			dispostion = 'Content-Disposition: form-data; name="auth"'
			tpl = "--%s\r\n%s\r\n\r\n%s\r\n--%s--\r\n" % (boundary, dispostion,
					"auth_string", boundary)
			self.assertEqual(tpl, body)
		
		round_tripper = tripper
		client.call_with_multipart("/hello", fields=[("auth", "auth_string")])

	def test_call_with_form(self):
		global round_tripper
		def tripper(client, method, path, body):
			self.assertEqual(body, "action=a&op=a&op=b")
			target_type = "application/x-www-form-urlencoded"
			self.assertEqual(client._header["Content-Type"], target_type)
			self.assertEqual(client._header["Content-Length"], len(body))
		
		round_tripper = tripper
		client.call_with_form("/hello", dict(op=["a", "b"], action="a"))

if __name__ == "__main__":
	unittest.main()
