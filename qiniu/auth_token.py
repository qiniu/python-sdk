# -*- coding: utf-8 -*-
import json
import base64
import time
import auth
import config

class PutPolicy(object):
	scope = None
	expires = 3600
	callbackUrl = None
	callbackBodyType = None
	customer = None
	asyncOps = None
	escape = None
	detectMime = None

	def __init__(self, scope):
		self.scope = scope

	def token(self):
		token = dict(
			scope = self.scope,
			deadline = int(time.time()) + self.expires,
		)

		if self.callbackUrl is not None:
			token["callbackUrl"] = self.callbackUrl

		if self.callbackBodyType is not None:
			token["callbackBodyType"] = self.callbackBodyType

		if self.customer is not None:
			token["customer"] = self.customer

		if self.asyncOps is not None:
			token["asyncOps"] = self.asyncOps

		if self.escape is not None:
			token["escape"] = self.escape

		if self.detectMime is not None:
			token["detectMime"] = self.detectMime
		
		return auth.sign_json(config.ACCESS_KEY, config.SECRET_KEY, token)

class GetPolicy(object):
	scope = None
	expires = 3600
	
	def token(self):
		token = dict(
			S = self.scope,
			E = self.expires + int(time.time())
		)
		return auth.sign_json(config.ACCESS_KEY, config.SECRET_KEY, token)

if __name__ == "__main__":
	config.ACCESS_KEY = "tGf47MBl1LyT9uaNv-NZV4XZe7sKxOIa9RE2Lp8B"
	config.SECRET_KEY = "zhbiA6gcQMEi22uZ8CBGvmbnD2sR8SO-5S8qlLCG"

	p = PutPolicy("a")
	# eyJzY29wZSI6ImEiLCJkZWFkbGluZSI6MTExMjIyMn0=
	print p.token()
	# tGf47MBl1LyT9uaNv-NZV4XZe7sKxOIa9RE2Lp8B:B6-2V-iikhegLkra9IvKnm8j3DE=:eyJzY29wZSI6ImEiLCJkZWFkbGluZSI6MTM2NDI2NDk5MX0=
