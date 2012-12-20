# -*- encoding: utf-8 -*-

import MultipartPostHandler
import urllib
import urllib2
from base64 import urlsafe_b64encode
import config
import utils


def __crc32checksum(localFile):
    with file(localFile, 'rb') as fh:
        return utils.crc32(fh.read())


def PutFile(url, bucket, key, mimeType, localFile, customMeta='', callbackParams='', enable_crc32_check=False):
    if mimeType == '':
        mimeType = 'application/octet-stream'
    entryURI = bucket + ':' + key
    action = '/rs-put/' + urlsafe_b64encode(entryURI) + '/mimeType/' + urlsafe_b64encode(mimeType)
    if customMeta != '':
        action += '/meta/' + urlsafe_b64encode(customMeta)
    if enable_crc32_check:
        action += '/crc32/' + str(__crc32checksum(localFile))
    params = {'file': file(localFile, 'rb'), 'action': action}
    if callbackParams != '':
        if isinstance(callbackParams, dict):
            callbackParams = urllib.urlencode(callbackParams)
        params['params'] = callbackParams
    opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
    return opener.open(url, params).read()


def UploadFile(bucket, key, mimeType, localFile, customMeta='', callbackParams='', upToken='', enable_crc32_check=False):
    if mimeType == '':
        mimeType = 'application/octet-stream'
    entryURI = bucket + ':' + key
    action = '/rs-put/' + urlsafe_b64encode(entryURI) + '/mimeType/' + urlsafe_b64encode(mimeType)
    if customMeta != '':
        action += '/meta/' + urlsafe_b64encode(customMeta)
    if enable_crc32_check:
        action += '/crc32/' + str(__crc32checksum(localFile))
    params = {'action': action, 'file': file(localFile, 'rb')}
    if callbackParams != '':
        if isinstance(callbackParams, dict):
            callbackParams = urllib.urlencode(callbackParams)
        params['params'] = callbackParams
    if upToken != '':
        params['auth'] = upToken
    url = config.UP_HOST + "/upload"
    opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
    return opener.open(url, params).read()
