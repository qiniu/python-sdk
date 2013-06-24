# -*- coding:utf-8 -*-
import json
import urllib

class BaseCall(object):
	def call_url(self, url):
		try:
			f = urllib.urlopen(url)
			body = json.loads(f.read())
			f.close()
		except IOError, e:
			return None, e
		except ValueError, e:
			return None, e
		
		if "error" in body:
			return None, body["error"]
		return body, None

class Exif(BaseCall):
	def make_request(self, url):
		return '%s?exif' % url

	def call(self, url):
		'''
		Directly call the url:
			if your bucket is public
				self.call(self.make_request(url))
			else
				self.call(GetPolicy.make_request(self.make_request(url)))
		'''
		return self.call_url(url)

class ImageView(object):
	mode = 1 # 1或2
	width = None # width 默认为0，表示不限定宽度
	height = None
	quality = None # 图片质量, 1-100
	format = None # 输出格式, jpg, gif, png, tif 等图片格式

	def make_request(self, url):
		target = []
		target.append('%s' % self.mode)
		
		if self.width is not None:
			target.append("w/%s" % self.width)

		if self.height is not None:
			target.append("h/%s" % self.height)

		if self.quality is not None:
			target.append("q/%s" % self.quality)

		if self.format is not None:
			target.append("format/%s" % self.format)

		return "%s?imageView/%s" % (url, '/'.join(target))


class ImageInfo(BaseCall):
	def make_request(self, url):
		return '%s?imageInfo' % url

	def call(self, url):
		'''
		Directly call the url:
			if your bucket is public
				self.call(self.make_request(url))
			else
				self.call(GetPolicy.make_request(self.make_request(url)))
		'''
		return self.call_url(url)
