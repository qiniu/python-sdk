#!/usr/bin/env python

import digestoauth
import eu

client = digestoauth.Client()

wm = eu.Service(client)

template = {"text":"hello",
			"dx":10,
			"dy":29
		}	

resp = wm.SetWatermark("user", template)
print '\n===> SetWatermark result:'
print resp

resp = wm.GetWatermark("user")
print '\n===> GetWatermark result:'
print resp