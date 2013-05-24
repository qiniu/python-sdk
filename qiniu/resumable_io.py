# -*- coding: utf-8 -*-
import os
import zlib
from base64 import urlsafe_b64encode

import auth_up
import config

_workers = 1
_task_queue_size = _workers * 4
_chunk_size = 256 * 1024
_try_times = 3
_block_size = 4 * 1024 * 1024

class Error(Exception):
	value = None
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

err_invalid_put_progress = Error("client: invalid put progress")
err_put_failed = Error("client: resumable put failed")
err_unmatched_checksum = Error("client: unmatched checksum")

def setup(chunk_size=0, try_times=0):
	"""
	 * chunk_size      => 默认的Chunk大小，不设定则为256k
	 * try_times       => 默认的尝试次数，不设定则为3
	"""
	global _chunk_size, _try_times

	if chunk_size == 0:
		chunk_size = 1 << 18

	if try_times == 0:
		try_times = 3

	_chunk_size, _try_times = chunk_size, try_times

# ----------------------------------------------------------
def gen_crc32(data):
	return zlib.crc32(data) & 0xffffffff

class PutExtra(object):
	callback_params = None # 当 uptoken 指定了 CallbackUrl，则 CallbackParams 必须非空
	bucket = None          # 当前是必选项，但未来会去掉
	custom_meta = None     # 可选。用户自定义 Meta，不能超过 256 字节
	mimetype = None        # 可选。在 uptoken 没有指定 DetectMime 时，用户客户端可自己指定 MimeType
	chunk_size = None      # 可选。每次上传的Chunk大小
	try_times = None       # 可选。尝试次数
	progresses = None      # 可选。上传进度
	notify = lambda self, idx, size, ret: None # 可选。进度提示
	notify_err = lambda self, idx, size, err: None

	def __init__(self, bucket):
		self.bucket = bucket

def put_file(uptoken, key, localfile, extra):
	""" 上传文件 """
	f = open(localfile, "rb")
	statinfo = os.stat(localfile)
	ret = put(uptoken, key, f, statinfo.st_size, extra)
	f.close()
	return ret

def put(uptoken, key, f, fsize, extra):
	""" 上传二进制流, 通过将data "切片" 分段上传 """
	if not isinstance(extra, PutExtra):
		print("extra must the instance of PutExtra")
		return

	block_cnt = block_count(fsize)
	if extra.progresses is None:
		extra.progresses = [None for i in xrange(0, block_cnt)]
	else:
		if not len(extra.progresses) == block_cnt:
			return None, err_invalid_put_progress

	if extra.try_times is None:
		extra.try_times = _try_times

	if extra.chunk_size is None:
		extra.chunk_size = _chunk_size

	client = auth_up.Client(uptoken)
	for i in xrange(0, block_cnt):
		try_time = extra.try_times
		read_length = _block_size
		if (i+1)*_block_size > fsize:
			read_length = fsize - i*_block_size
		data_slice = f.read(read_length)
		while True:
			err = resumable_block_put(client, data_slice, i, extra)
			if err is None:
				break

			try_time -= 1
			if try_time <= 0:
				return None, err_put_failed
			print err, ".. retry"

	return mkfile(client, key, fsize, extra)

# ----------------------------------------------------------

def resumable_block_put(client, block, index, extra):
	block_size = len(block)

	if extra.progresses[index] is None or "ctx" not in extra.progresses[index]:
		end_pos = extra.chunk_size-1
		if block_size < extra.chunk_size:
			end_pos = block_size-1
		chunk = block[: end_pos]
		crc32 = gen_crc32(chunk)
		chunk = bytearray(chunk)
		extra.progresses[index], err = mkblock(client, block_size, chunk)
		if not extra.progresses[index]["crc32"] == crc32:
			return err_unmatched_checksum
		if err is not None:
			extra.notify_err(index, end_pos + 1, err)
			return err
		extra.notify(index, end_pos + 1, extra.progresses[index])

	while extra.progresses[index]["offset"] < block_size:
		offset = extra.progresses[index]["offset"]
		chunk = block[offset: offset+extra.chunk_size-1]
		crc32 = gen_crc32(chunk)
		chunk = bytearray(chunk)
		extra.progresses[index], err = putblock(client, extra.progresses[index], chunk)
		if not extra.progresses[index]["crc32"] == crc32:
			return err_unmatched_checksum
		if err is not None:
			extra.notify_err(index, len(chunk), err)
			return err
		extra.notify(index, len(chunk), extra.progresses[index])

def block_count(size):
	global _block_size
	return size / _block_size + 1

def mkblock(client, block_size, first_chunk):
	url = "http://%s/mkblk/%s" % (config.UP_HOST, block_size)
	content_type = "application/octet-stream"
	return client.call_with(url, first_chunk, content_type, len(first_chunk))

def putblock(client, block_ret, chunk):
	url = "%s/bput/%s/%s" % (block_ret["host"], block_ret["ctx"], block_ret["offset"])
	content_type = "application/octet-stream"
	return client.call_with(url, chunk, content_type, len(chunk))

def mkfile(client, key, fsize, extra):
	encoded_entry = urlsafe_b64encode("%s:%s" % (extra.bucket, key))
	url = ["http://%s/rs-mkfile/%s/fsize/%s" % (config.UP_HOST, encoded_entry, fsize)]

	if extra.mimetype:
		url.append("mimeType/%s" % urlsafe_b64encode(extra.mimetype))

	if extra.custom_meta:
		url.append("meta/%s" % urlsafe_b64encode(extra.custom_meta))

	if extra.callback_params:
		url.append("params/%s" % urlsafe_b64encode(extra.callback_params))

	url = "/".join(url)
	body = ",".join([i["ctx"] for i in extra.progresses])
	return client.call_with(url, body, "text/plain", len(body))
