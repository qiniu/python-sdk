#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli
import time

client = simpleoauth2.Client()
client.ExchangeByPassword('test@qbox.net', 'test')

tblName = 'tblName'
#uniqkey = 'errno-404'
uniqkey = 'test-file-uniqkey-%f' % time.time()

rs = qboxrs.Service(client, tblName)

resp = rs.PutAuth()
print '\n===> PutAuth %s result:' % uniqkey
print resp

resp = rscli.PutFile(resp['url'], tblName, uniqkey, '', __file__, 'CustomData', {'key': uniqkey})
print '\n===> PutFile %s result:' % uniqkey
print resp

resp = rs.Stat(uniqkey)
print '\n===> Stat %s result:' % uniqkey
print resp

resp = rs.Delete(uniqkey)
print '\n===> Delete %s result:' % uniqkey
print resp
