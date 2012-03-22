#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli

client = simpleoauth2.Client()
client.ExchangeByPassword('test@qbox.net', 'test')

tblName = 'tblName'
key = '2.jpg'

rs = qboxrs.Service(client, tblName)

resp = rs.PutAuth()
print '\n===> PutAuth %s result:' % key
print resp

resp = rscli.PutFile(str(resp['url']), tblName, key, '', key)
print '\n===> PutFile %s result:' % key
print resp

resp = rs.Stat(key)
print '\n===> Stat %s result:' % key
print resp

