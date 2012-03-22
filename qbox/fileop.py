from base64 import urlsafe_b64encode

def MakeStyleURL(url, templPngFile, params, quality = 85):
	"""
	 * func MakeStyleURL(url string, templPngFile string, params string, quality int) => (urlMakeStyle string)
	"""
	return url + '/makeStyle/' + urlsafe_b64encode(templPngFile) + '/params/' + urlsafe_b64encode(params) + '/quality/' + quality

def ImagePreviewURL(url, thumbType):
	"""
	 * func ImagePreviewURL(url string, thumbType int) => (urlImagePreview string)
	"""
	return url + '/imagePreview/' + thumbType

def ImageMogrURL(url, params):
	"""
	 * func ImagePreviewURL(url string, thumbType int) => (urlImagePreview string)
	"""
	return url + '/imageMogr/' + params

def ImageInfoURL(url):
	"""
	 * func ImageInfoURL(url string) => (urlImageInfo string)
	"""
	return url + '/imageInfo'

def Image90x90URL(url):
	url2 = url + '/imageMogr/auto-orient/thumbnail/!90x90r/gravity/center/crop/90x90'
	print url2
	return url2
