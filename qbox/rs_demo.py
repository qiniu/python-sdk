#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli
import config
import time

client = simpleoauth2.Client()
client.ExchangeByPassword('test@qbox.net', 'test')

tblName = 'tblName'
uniqkey = 'test-file-uniqkey-%f' % time.time()

rs = qboxrs.Service(client, tblName)

resp = rs.PutAuth()
print '\n===> PutAuth %s result:' % uniqkey
print resp

resp = rscli.PutFile(resp['url'], tblName, uniqkey, '', __file__, 'CustomData', {'key': uniqkey})
print '\n===> PutFile %s result:' % uniqkey
print resp

resp = rs.Publish(config.DEMO_DOMAIN + '/' + tblName)
print '\n===> Publish result:'
print resp

resp = rs.Stat(uniqkey)
print '\n===> Stat %s result:' % uniqkey
print resp

resp = rs.Get(uniqkey, uniqkey)
print '\n===> Get %s result:' % uniqkey
print resp

resp = rs.GetIfNotModified(uniqkey, uniqkey, resp['hash'])
print '\n===> GetIfNotModified %s result:' % uniqkey
print resp

print '\n===> Display %s contents:' % uniqkey
print urllib.urlopen(resp['url']).read()

action='delete'
if action == 'delete':
	resp = rs.Delete(uniqkey)
	print '\n===> Delete %s result:' % uniqkey
	print resp
elif action == 'drop':
	resp = rs.Drop()
	print '\n===> Drop table result:'
	print resp

