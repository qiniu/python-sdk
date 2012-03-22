#!/usr/bin/env python

import urllib
import simpleoauth2
import fileop
import rs as qboxrs

client = simpleoauth2.Client()
client.ExchangeByPassword('test@qbox.net', 'test')

tblName = 'tblName'
key = '2.jpg'

rs = qboxrs.Service(client, tblName)

resp = rs.Get(key, key)
print '\n===> Get %s result:' % key
print resp

urlImageInfo = fileop.ImageInfoURL(resp['url'])

print "\n===> ImageInfo of %s:\n" % key
print urllib.urlopen(urlImageInfo).read()
print

urlImagePreview = fileop.Image90x90URL(resp['url'])

print "\n===> ImagePreview of %s:\n" % key
f = open("2.preview.jpg", "w")
f.write(urllib.urlopen(urlImagePreview).read())
f.close()
print

