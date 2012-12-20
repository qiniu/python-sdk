#!/usr/bin/env python

from qiniu import config
import urllib
from qiniu import fileop
from qiniu import rs as qiniurs
from qiniu import digestoauth
from qiniu import uptoken
from qiniu import rscli

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

bucket = 'test_photos'
key = 'test.jpg'
targetKey = 'cropped-' + key


tokenObj = uptoken.UploadToken(bucket, 3600)
uploadToken = tokenObj.generate_token()
print "Upload Token is: %s" % uploadToken

resp = rscli.UploadFile(bucket, key, 'image/jpg', key, '', '', uploadToken)
print '\n===> UploadFile %s result:' % key
print resp


client = digestoauth.Client()
rs = qiniurs.Service(client, bucket)

resp = rs.Get(key, key)
print '\n===> Get %s result:' % key
print resp

urlImageInfo = fileop.ImageInfoURL(resp['url'])
print "\n===> ImageInfo of %s:" % key
print urllib.urlopen(urlImageInfo).read()

urlImageSource = resp['url']
opts = {
    "thumbnail": "!120x120r",
    "gravity": "center",
    "crop": "!120x120a0a0",
    "quality": 85,
    "rotate": 45,
    "format": "jpg",
    "auto_orient": True,
}

mogrifyPreviewURL = fileop.ImageMogrifyPreviewURL(urlImageSource, opts)
print "\n===> ImageMogrifyPreviewURL result:"
print mogrifyPreviewURL

imgrs = qiniurs.Service(client, "test_thumbnails_bucket")
resp = imgrs.ImageMogrifyAs(targetKey, urlImageSource, opts)
print "\n===> ImageMogrifyAs %s result:" % targetKey
print resp
