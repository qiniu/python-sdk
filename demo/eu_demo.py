#!/usr/bin/env python

from qiniu import config
from qiniu import digestoauth
from qiniu import rscli
from qiniu import rs as qiniurs
from qiniu import uptoken
from qiniu import eu

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

bucket = 'test_photos'
key = 'test.jpg'
customer = 'end_user_id'
demo_domain = 'test_photos1.dn.qbox.me'

client = digestoauth.Client()
rs = qiniurs.Service(client, bucket)

rs.SetProtected(1)
rs.SetSeparator("-")
rs.SetStyle("gsmall", "imageView/0/w/64/h/64/watermark/0")
rs.SetStyle("gmiddle", "imageView/0/w/256/h/256/watermark/1")
rs.SetStyle("glarge", "imageView/0/w/512/h/512/wartermark/1")

wm = eu.Service(client)
template = {"text": "hello", "dx": 1, "dy": 19, "bucket": bucket}
resp = wm.SetWatermark(customer, template)
print '\n===> SetWatermark %s result:' % customer
print resp

tokenObj = uptoken.UploadToken(bucket, 3600, "", "", customer)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

resp = rscli.UploadFile(bucket, key, 'image/jpg', key, '', '', uploadToken)
print '\n===> UploadFile %s result:' % key
print resp

resp = rs.Publish(demo_domain)
print '\n===> Publish Domain %s result:' % demo_domain
print resp

resp = rs.Unpublish(demo_domain)
print '\n===> Unpublish Domain %s result:' % demo_domain
print resp
