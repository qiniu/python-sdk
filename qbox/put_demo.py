#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli
import digestoauth
import uptoken

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

bucket = 'test_photos'
key = 'test.jpg'
customer = 'end_user_id'
demo_domain = 'test_photos.dn.qbox.me'

tokenObj = uptoken.UploadToken(bucket, 3600, "", "", customer)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

resp = rscli.UploadFile(bucket, key, 'image/jpg', key, '', '', uploadToken)
print '\n===> UploadFile %s result:' % key
print resp

client = digestoauth.Client()
rs = qboxrs.Service(client, bucket)

resp = rs.Stat(key)
print '\n===> Stat %s result:' % key
print resp
