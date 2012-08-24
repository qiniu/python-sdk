#!/usr/bin/env python

import urllib
import digestoauth 
import rs as qboxrs
import rscli
import config
import uptoken

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

DEMO_DOMAIN = 'book.dn.qbox.me'

client = digestoauth.Client()

bucket = 'bucket'
newbucket = "newbucket"
key = 'demo.jpg'
customer = "boy"

rs = qboxrs.Service(client, bucket)

uptoken = uptoken.UploadToken(bucket, 3600, "", "", customer).generate_token()
resp = rscli.UploadFile(bucket, key, 'image/jpg', '/home/ygao/demo.jpg', '', '', uptoken)
print '\n===> UploadFile %s result:' % key
print resp

resp = rs.Publish(DEMO_DOMAIN)
print '\n===> Publish result:'
print resp

resp = rs.Stat(key)
print '\n===> Stat %s result:' % key
print resp

resp = rs.Get(key, key)
print '\n===> Get %s result:' % key
print resp

resp = rs.GetIfNotModified(key, key, resp['hash'])
print '\n===> GetIfNotModified %s result:' % key
print resp

print '\n===> Display %s contents:' % key
print urllib.urlopen(resp['url']).read()

resp = rs.Delete(key)
print '\n===> Delete %s result:' % key
print resp

resp = rs.Mkbucket(newbucket)
print '\n===> Mkucket %s result:' % newbucket
print resp

resp = rs.Buckets()
print '\n===> Buckets result:'
print resp

resp = rs.Drop(newbucket)
print '\n===> Drop %s result:' % newbucket
print resp