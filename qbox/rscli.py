import MultipartPostHandler
import urllib
import urllib2
from base64 import urlsafe_b64encode
import config

def PutFile(url, bucket, key, mimeType, localFile, customMeta = '', callbackParams = ''):

	if mimeType == '':
		mimeType = 'application/octet-stream'

	entryURI = bucket + ':' + key
	action = '/rs-put/' + urlsafe_b64encode(entryURI) + '/mimeType/' + urlsafe_b64encode(mimeType)
	if customMeta != '':
		action += '/meta/' + urlsafe_b64encode(customMeta)
	params = {'file' : file(localFile, 'rb'), 'action': action}
	if callbackParams != '':
		if isinstance(callbackParams, dict):
			callbackParams = urllib.urlencode(callbackParams)
		params['params'] = callbackParams
	opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)

	return opener.open(url, params).read()

def UploadFile(bucket, key, mimeType, localFile, customMeta = '', callbackParams = '', upToken = ''):

	if mimeType == '':
		mimeType = 'application/octet-stream'

	entryURI = bucket + ':' + key
	action = '/rs-put/' + urlsafe_b64encode(entryURI) + '/mimeType/' + urlsafe_b64encode(mimeType)
	if customMeta != '':
		action += '/meta/' + urlsafe_b64encode(customMeta)
		
	params = {'action': action, 'file' : file(localFile, 'rb')}

	if callbackParams != '':
		if isinstance(callbackParams, dict):
			callbackParams = urllib.urlencode(callbackParams)
		params['params'] = callbackParams
	
	if upToken != '':
		params['auth'] = upToken

	url = config.UP_HOST + "/upload"
	opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)	
	return opener.open(url, params).read()

