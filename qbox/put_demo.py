#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli
import digestoauth
import uptoken

client = digestoauth.Client()
bucket = 'bucket'
key = 'demo.jpg'
customer = 'boy'

rs = qboxrs.Service(client, bucket)

uptoken = uptoken.UploadToken(bucket, 3600, "", "", customer).generate_token()
resp = rscli.UploadFile(bucket, key, 'image/jpg', '/home/ygao/demo.jpg', '', '', uptoken)
print '\n===> UploadFile %s result:' % key
print resp

resp = rs.Stat(key)
print '\n===> Stat %s result:' % key
print resp