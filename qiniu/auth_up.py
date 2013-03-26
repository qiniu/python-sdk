# -*- coding: utf-8 -*-
import config

import auth

def setup():
	pass

class Client(auth.Client):
	up_token = None
	
	def __init__(self, up_token, host=None):
		if host is None:
			host = config.UP_HOST
		self.up_token = up_token
		super(Client, self).__init__(host)

	def round_tripper(self, method, path, body):
		self.set_header("Authorization", "UpToken %s" % self.up_token)
		return super(Client, self).round_tripper(method, path, body)
