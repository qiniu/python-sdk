# -*- coding: utf-8 -*-
import config
from urlparse import urlparse
import hmac
from hashlib import sha1
from base64 import urlsafe_b64encode

import rpc

class Mac(object):
	access = None
	secret = None
	def __init__(self, access=None, secret=None):
		if access is None and secret is None:
			access, secret = config.ACCESS_KEY, config.SECRET_KEY
		self.access, self.secret = access, secret

	def __sign(self, data):
		hashed = hmac.new(self.secret, data, sha1)
		return urlsafe_b64encode(hashed.digest())

	def sign(self, data):
		return '%s:%s' % (self.access, self.__sign(data))

	def sign_with_data(self, b):
		data = urlsafe_b64encode(b)
		return '%s:%s:%s' % (self.access, self.__sign(data), data)

	def sign_request(self, path, body, content_type):
		parsedurl = urlparse(path)
		p_query = parsedurl.query
		p_path = parsedurl.path
		data = p_path
		if p_query != "":
			data = ''.join([data, '?', p_query])
		data = ''.join([data, "\n"])

		if body:
			incBody = [
				"application/x-www-form-urlencoded",
			]
			if content_type in incBody:
				data += body

		return '%s:%s' % (self.access, self.__sign(data))


class Client(rpc.Client):
	def __init__(self, host, mac=None):
		if mac is None:
			mac = Mac()
		super(Client, self).__init__(host)
		self.mac = mac

	def round_tripper(self, method, path, body):
		token = self.mac.sign_request(path, body, self._header.get("Content-Type"))
		self.set_header("Authorization", "QBox %s" % token)
		return super(Client, self).round_tripper(method, path, body)
