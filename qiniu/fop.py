# -*- coding:utf-8 -*-
import json
import urllib

import auth

class BaseCall(object):
	def call_url(self, url):
		try:
			f = urllib.urlopen(self.make_request(url))
			body = json.loads(f.read())
			f.close()
		except IOError, e:
			return None, e
		except ValueError, e:
			return None, e
		
		if "error" in body:
			return None, body["error"]
		return body, None

class ImageExif(BaseCall):
	def make_request(self, url):
		return '%s?exif' % url

	def call(self, url):
		return self.call_url(url)

class ImageView(object):
	mode = 1 # 1或2
	width = None # width 默认为0，表示不限定宽度
	height = None
	quality = None # 图片质量, 1-100
	format = None # 输出格式, jpg, gif, png, tif 等图片格式

	def make_request(self, url):
		target = []
		if not self.mode == 1 and not self.mode == 2:
			return 
		target.append('%s' % self.mode)
		
		if self.width is not None:
			target.append("w/%s" % self.width)

		if self.height is not None:
			target.append("h/%s" % self.height)

		if self.quality is not None:
			target.append("q/%s" % self.quality)

		if self.format is not None:
			target.append("format/%s" % self.format)

		return "%s?imageView/%s/" % (url, '/'.join(target))

class ImageMogr(object):
	auto_orient = False # 根据原图EXIF信息自动旋正
	thumbnail = None # 缩略图尺寸
	gravity = None
	crop = None # 裁剪尺寸
	quality = None # 质量
	rotate = None # 旋转角度, 单位为度
	format = None # png, jpg等图片格式

	def make_request(self, url):
		target = []
		if self.auto_orient:
			target.append("auto-orient")

		if self.thumbnail is not None:
			target.append("thumbnail/%s" % self.thumbnail)

		if self.gravity is not None:
			target.append("gravity/%s" % self.gravity)

		if self.crop is not None:
			target.append("crop/%s" % self.crop)

		if self.quality is not None:
			target.append("quality/%s" % self.quality)

		if self.rotate is not None:
			target.append("rotate/%s" % self.rotate)

		if self.format is not None:
			target.append("format/%s" % self.format)

		return "%s?imageMogr/%s" % (url , '/'.join(target))

class ImageInfo(BaseCall):
	def make_request(self, url):
		return '%s?imageInfo' % url

	def call(self, url):
		return self.call_url(url)
