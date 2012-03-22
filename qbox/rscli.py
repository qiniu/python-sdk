
import MultipartPostHandler
import urllib
import urllib2
from base64 import urlsafe_b64encode

def PutFile(url, tblName, key, mimeType, localFile, customMeta = '', callbackParams = ''):

	if mimeType == '':
		mimeType = 'application/octet-stream'

	entryURI = tblName + ':' + key
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

