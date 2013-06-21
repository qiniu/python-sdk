# -*- coding: utf-8 -*-
import json
import base64
import time
import rpc
import config
import urllib
import auth_digest

class PutPolicy(object):
	scope = None             # 可以是 bucketName 或者 bucketName:key
	expires = 3600           # 默认是 3600 秒
	callbackUrl = None
	callbackBodyType = None
	customer = None
	asyncOps = None         
	escape = None            # 非 0 表示 Callback 的 Params 支持转义符
	detectMime = None        # 非 0 表示在服务端自动检测文件内容的 MimeType

	def __init__(self, scope):
		self.scope = scope

	def token(self, mac=auth_digest.Mac()):
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
		
		b = json.dumps(token, separators=(',',':'))
		return mac.sign_with_data(b)

class GetPolicy(object):
	expires = 3600
	def __init__(self):
		pass
	
	def make_request(base_url, mac=auth_digest.Mac()):
		'''
		 *  return private_url
		'''
		deadline = int(time.time()) + self.expires
		if '?' in base_url:
			base_url += '&'
		else:
			base_url += '?'
		base_url = '%se=%s' % (base_url, str(deadline))

		token = mac.sign(base_url)
		return '%s&token=%s' % (base_url, token)


def make_base_url(domain, key):
	'''
	 * domain => str
	 * key => str
	 * return base_url
	'''
	return ''.join(['http://', domain, '/', urllib.quote(key)])
