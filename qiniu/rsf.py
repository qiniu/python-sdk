# -*- coding: utf-8 -*-
import auth_digest
import config
import urllib

class Rsf(object):
	conn = None
	def __init__(self, mac=None):
		if mac is None:
			mac = auth_digest.Mac()
		self.conn = auth_digest.Client(host=config.RSF_HOST, mac=mac)
		
	def list_prefix(self, bucket, prefix=None, marker=None, limit=None):
		'''
		 * bucket => str
		 * prefix => str
		 * marker => str
		 * limit => int
		'''
		ops = {
			'bucket': bucket,
		}
		if marker is not None:
			ops['marker'] = marker
		if limit is not None:
			ops['limit'] = limit
		if prefix is not None:
			ops['prefix'] = prefix
		url = '%s?%s' % ('/list', urllib.urlencode(ops))
		return self.conn.call_with(url, body=None, content_type='application/x-www-form-urlencoded')
