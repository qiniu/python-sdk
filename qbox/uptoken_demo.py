#!/usr/bin/env python

import config
import uptoken


config.ACCESS_KEY = '<Please apply your access key>'
config.SECRET_KEY = '<Dont send your secret key to anyone>'

tokenObj = uptoken.UploadToken('test_bucket', 3600)
# tokenObj.set('scope', 'another_test_bucket')
# tokenObj.set('expires_in', 86400)
# tokenObj.set('callback_url', 'http://example.com/callback')
# tokenObj.set('return_url', 'http://example.com/return')
print "Upload Token is: %s" % tokenObj.generate_token()

