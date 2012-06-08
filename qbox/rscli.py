
import MultipartPostHandler
import urllib
import urllib2
from base64 import urlsafe_b64encode
from ctypes import *
import binascii

def PutFile(url, tblName, key, mimeType, localFile, customMeta = '', callbackParams = '', enableCRC32Check = False):
    if mimeType == '':
        mimeType = 'application/octet-stream'
    entryURI = tblName + ':' + key
    action = '/rs-put/' + urlsafe_b64encode(entryURI) + '/mimeType/' + urlsafe_b64encode(mimeType)
    if customMeta != '':
        action += '/meta/' + urlsafe_b64encode(customMeta)
    if enableCRC32Check == True:
        action += '/crc32/' + str(getFileCRC(localFile))
    params = {'file' : file(localFile, 'rb'), 'action': action}
    if callbackParams != '':
        if isinstance(callbackParams, dict):
            callbackParams = urllib.urlencode(callbackParams)
        params['params'] = callbackParams
    opener = urllib2.build_opener(MultipartPostHandler.MultipartPostHandler)
    return opener.open(url, params).read()

def getFileCRC(_path):
    try:
        blocksize = 1024 * 64
        f = open(_path,"rb")
        str = f.read(blocksize)
        crc = 0
        while(len(str) != 0):
            crc = binascii.crc32(str, crc)
            str = f.read(blocksize)
            f.close()
    except:
        klog.error("get file crc error!")
        return 0
    return c_uint(crc).value
