# -*- coding: utf-8 -*-
import auth.digest
import conf
import urllib

class Client(object):
	conn = None
	def __init__(self, mac=None):
		if mac is None:
			mac = auth.digest.Mac()
		self.conn = auth.digest.Client(host=conf.RSF_HOST, mac=mac)
		
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
		ret, err = self.conn.call_with(url, body=None, content_type='application/x-www-form-urlencoded')
		if not ret.get('marker'):
			err = 'EOF'
		return ret, err
