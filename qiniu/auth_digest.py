# -*- coding: utf-8 -*-
import config
from urlparse import urlparse

import rpc

class Client(rpc.Client):
	def __init__(self):
		super(Client, self).__init__(config.RS_HOST)

	def make_signal(self, path, body):
		parsedurl = urlparse(path)
		p_query = parsedurl.query
		p_path = parsedurl.path
		data = p_path
		if p_query != "":
			data = ''.join([data, '?', p_query])
		data = ''.join([data, "\n"])
		
		if body != None and "Content-Type" in self._header and \
			self._header["Content-Type"] == "application/x-www-form-urlencoded":
			data += body

		return rpc.sign(config.SECRET_KEY, data)

	def round_tripper(self, method, path, body):
		digest = self.make_signal(path, body)
		self.set_header("Authorization", "QBox %s:%s" % (config.ACCESS_KEY, digest))
		return super(Client, self).round_tripper(method, path, body)
