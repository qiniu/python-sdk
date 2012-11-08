#!/usr/bin/env python

import config
import uptoken
import up

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'


bucket = 'test_photos'
key = 'test.jpg'

tokenObj = uptoken.UploadToken(bucket, 3600)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

upService = up.UpService(up.Client(uploadToken))

callRet = up.ResumablePutFile(upService, bucket, key, 'image/jpeg', key)

resp = None
if callRet != None and callRet.ok():
    resp = callRet.content
print '\n===> resumablePutFile %s result:' % key
print resp
