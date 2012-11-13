#!/usr/bin/env python
from qbox import digestoauth
from qbox import rs as qboxrs
from qbox import rscli
from qbox import config
from qbox import uptoken

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

DEMO_DOMAIN = 'test_photos3.dn.qbox.me'

bucket = 'test_photos'
newbucket = "new_test_bucket3"
key = 'test.jpg'
customer = 'end_user_id'

tokenObj = uptoken.UploadToken(bucket, 3600, "", "", customer)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

resp = rscli.UploadFile(bucket, key, 'image/jpg', key, '', '', uploadToken)
print '\n===> UploadFile %s result:' % key
print resp


client = digestoauth.Client()
rs = qboxrs.Service(client, bucket)

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

# print '\n===> Display %s contents:' % key
# print urllib.urlopen(resp['url']).read()

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

resp = rs.Unpublish(DEMO_DOMAIN)
print '\n===> Unpublish Domain %s result:' % DEMO_DOMAIN
print resp
