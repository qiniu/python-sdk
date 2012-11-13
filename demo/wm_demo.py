#!/usr/bin/env python

from qbox import config
from qbox import digestoauth
from qbox import eu

config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

client = digestoauth.Client()
wm = eu.Service(client)

template = {"text": "hello", "dx": 10, "dy": 29}
resp = wm.SetWatermark("user", template)
print '\n===> SetWatermark result:'
print resp

resp = wm.GetWatermark("user")
print '\n===> GetWatermark result:'
print resp
