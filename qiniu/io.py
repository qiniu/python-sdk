# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode
import rpc
import conf
import zlib

UNDEFINED_KEY = "?"


class PutExtra(object):
	params = {}
	mime_type = 'application/octet-stream'
	crc32 = ""
	check_crc = 0


def put(uptoken, key, data, extra=None):
	""" put your data to Qiniu

	key, your resource key. if key is None, Qiniu will generate one.
	data may be str or read()able object.
	"""
	fields = {
	}

	if not extra:
		extra = PutExtra()

	if extra.params:
		for key in extra.params:
			fields[key] = str(extra.params[key])

	if extra.check_crc:
		fields["crc32"] = str(extra.crc32)

	if key is not None:
		fields['key'] = key

	fields["token"] = uptoken

	fname = key
	if fname is None:
		fname = UNDEFINED_KEY
	elif fname is '':
		fname = 'index.html'
	files = [
		{'filename': fname, 'data': data, 'mime_type': extra.mime_type},
	]
	return rpc.Client(conf.UP_HOST).call_with_multipart("/", fields, files)


def put_file(uptoken, key, localfile, extra=None):
	""" put a file to Qiniu

	key, your resource key. if key is None, Qiniu will generate one.
	"""
	with open(localfile) as f:
		if extra is not None and extra.check_crc == 1:
			extra.crc32 = _file_crc32(f)
		f.seek(0, 0)
		return put(uptoken, key, f, extra)


def get_url(domain, key, dntoken):
	return "%s/%s?token=%s" % (domain, key, dntoken)


def _file_crc32(f):
	#TODO 大文件时内存优化
	return zlib.crc32(f.read()) & 0xFFFFFFFF
