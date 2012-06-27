#!/usr/bin/env python

import urllib
import digestoauth 
import rs as qboxrs
import rscli
import config

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

DEMO_DOMAIN = 'iovip.qbox.me/bucket'

client = digestoauth.Client()

bucket = 'bucket'
key = 'rs_demo.py'

rs = qboxrs.Service(client, bucket)

resp = rs.Drop()
print '\n===> Drop %s result:' % key
print resp

resp = rs.PutAuth()
print '\n===> PutAuth %s result:' % key
print resp

resp = rscli.PutFile(resp['url'], bucket, key, '', __file__, 'CustomData', {'key': key})
print '\n===> PutFile %s result:' % key
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

