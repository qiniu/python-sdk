#!/usr/bin/env python

import urllib
import simpleoauth2
import fileop
import rs as qboxrs
import digestoauth

client = digestoauth.Client()

bucket = 'book'
key = 'test.jpg'
targetKey = 'cropped-' + key

rs = qboxrs.Service(client, bucket)

resp = rs.Get(key, key)
print '\n===> Get %s result:' % key
print resp

urlImageInfo = fileop.ImageInfoURL(resp['url'])
print "\n===> ImageInfo of %s:" % key
print urllib.urlopen(urlImageInfo).read()

urlImageSource = resp['url']
opts = {	
	"thumbnail":"!120x120r",
   	"gravity":"center",
   	"crop":"!120x120a0a0",
    	"quality":85,
    	"rotate":45,
    	"format":"jpg",
    	"auto_orient":True
}

mogrifyPreviewURL = fileop.ImageMogrifyPreviewURL(urlImageSource, opts)
print "\n===> ImageMogrifyPreviewURL result:"
print mogrifyPreviewURL

imgrs = qboxrs.Service(client, "test_thumbnails_bucket")
resp = imgrs.ImageMogrifyAs(targetKey, urlImageSource, opts)
print "\n===> ImageMogrifyAs %s result:" % targetKey
print resp
