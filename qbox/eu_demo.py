#!/usr/bin/env python

import digestoauth
import rscli
import rs as qboxrs
import uptoken
import eu

bucket = 'book'
key = 'demo.jpg'
customer = 'boy'
demo_domain = 'book.dn.qbox.me'

client = digestoauth.Client()
rs = qboxrs.Service(client, bucket)

rs.SetProtected(1)
rs.SetSeparator("-")
rs.SetStyle("gsmall", "imageView/0/w/64/h/64/watermark/0")
rs.SetStyle("gmiddle", "imageView/0/w/256/h/256/watermark/1")
rs.SetStyle("glarge", "imageView/0/w/512/h/512/wartermark/1")

wm = eu.Service(client)
template = {"text":"hello",
			"dx":1,
			"dy":19,
			"bucket":bucket
		}	
wm.SetWatermark(customer, template)

uptoken = uptoken.UploadToken(bucket, 3600, "", "", customer).generate_token()
resp = rscli.UploadFile(bucket, key, 'image/jpg', '/home/ygao/demo.jpg', '', '', uptoken)

rs.Publish(demo_domain)