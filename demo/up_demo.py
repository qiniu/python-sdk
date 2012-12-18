#!/usr/bin/env python

from qbox import config
from qbox import uptoken
from qbox import up

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

bucket = 'test_photos'
key = 'test.jpg'

tokenObj = uptoken.UploadToken(bucket, 3600)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

resp = up.ResumablePutFile(uploadToken, bucket, key, 'image/jpeg', key)

print '\n===> resumablePutFile %s result:' % key
print resp
