# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode
import rpc
import config
import zlib

UNDEFINED_KEY = "?"

class PutExtra(object):
	callback_params = None
	bucket = None
	custom_meta = None
	mime_type = None
	crc32 = ""
	check_crc = 0
	def __init__(self, bucket):
		self.bucket = bucket
		self.file_crc32 = ""

def put(uptoken, key, data, extra):
	action = ["/rs-put"]
	action.append(urlsafe_b64encode("%s:%s" % (extra.bucket, key)))
	if extra.mime_type is not None:
		action.append("mimeType/%s" % urlsafe_b64encode(extra.mime_type))

	if extra.custom_meta is not None:
		action.append("meta/%s" % urlsafe_b64encode(extra.custom_meta))

	if extra.check_crc:
		real_crc32 = extra.crc32
		if extra.check_crc == 1:
			real_crc32 = extra.file_crc32
		action.append("crc32/%s" % real_crc32)

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
	if extra.check_crc == 1:
		extra.file_crc32 = zlib.crc32(data) & 0xFFFFFFFF
	return put(uptoken, key, data, extra)

def get_url(domain, key, dntoken):
	return "%s/%s?token=%s" % (domain, key, dntoken)

