# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode
import rpc
import config

class PutExtra(object):
	callback_params = None
	bucket = None
	custom_meta = None
	mime_type = None
	def __init__(self, bucket):
		self.bucket = bucket

def put(uptoken, key, data, extra):
	action = ["/rs-put"]
	action.append(urlsafe_b64encode("%s:%s" % (extra.bucket, key)))
	if extra.mime_type is not None:
		action.append("mimeType/%s" % urlsafe_b64encode(extra.mime_type))

	if extra.custom_meta is not None:
		action.append("meta/%s" % urlsafe_b64encode(extra.custom_meta))
	
	fields = [
		("action", '/'.join(action)),
		("auth", uptoken),
	]
	if extra.callback_params is not None:
		fields.append(("params", extra.callback_params))

	files = [
		("file", key, data)
	]
	return rpc.Client(config.UP_HOST).call_with_multipart("/upload", fields, files)

def put_file(uptoken, key, localfile, extra):
	f = open(localfile)
	data = f.read()
	f.close()
	return put(uptoken, key, data, extra)

def get_url(domain, key, dntoken):
	return "%s/%s?token=%s" % (domain, key, dntoken)

