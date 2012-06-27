#!/usr/bin/env python

import urllib
import simpleoauth2
import digestoauth 
import rs as qboxrs
import rscli
import config

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

resp = rs.Publish(config.DEMO_DOMAIN + '/' + bucket)
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

action=''
if action == 'delete':
	resp = rs.Delete(key)
	print '\n===> Delete %s result:' % key
	print resp
elif action == 'drop':
	resp = rs.Drop()
	print '\n===> Drop table result:'
	print resp

