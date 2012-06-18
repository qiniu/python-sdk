#!/usr/bin/env python

import urllib
import simpleoauth2
import rs as qboxrs
import rscli
import config
import traceback
import os
import filecmp

tblName = 'zyxtest1'
key = 'testcase.py'
fileName = 'rs_demo.py'
fileName2 = 'config.py'
downLoadFileName = 'Download'

class TestCase:
	
	def SetUp(self):
		client = simpleoauth2.Client()
		try:
			client.ExchangeByPassword('qboxtest', 'qboxtest123')
			self.rs = qboxrs.Service(client, tblName)
		except Exception,data:
			print Exception,":",data
			return False
		return True

	def TestPutAuth(self):
		try:
			resp = self.rs.PutAuth()
		except Exception,data:
			print Exception,":",data
			return 1
		return 0

	def TestPutDelete(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp = rs.Delete(key)
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		return 0

	def TestPutDrop(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			key1 = 'file1'
			resp1 = rscli.PutFile(resp['url'], tblName, key1, '', fileName, 'CustomData', {'key': key1})
			key2 = 'file2'
			resp2 = rscli.PutFile(resp['url'], tblName, key2, '', fileName, 'CustomData', {'key': key2})
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		return 0


	def TestPutDuplicate_Same(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp2 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		return 0

	def TestPutDuplicate_Diff(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp2 = rscli.PutFile(resp['url'], tblName, key, '', fileName2, 'CustomData', {'key': key})
		except Exception,data:
			#print Exception,":",data
			#print traceback.print_exc()
			return 0
		return 1

	def TestPutUnfind(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', 'icannotfind', 'CustomData', {'key': key})
		except Exception,data:
			return 0
		return 1

	def TestStat(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp = rs.Stat(key)
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		return 0

	def TestStatKeyUnfind(self):
		rs = self.rs
		try:
			resp = rs.Stat('icannotfind')
		except Exception,data:
			#print Exception,":",data
			#print traceback.print_exc()
			return 0
		return 1

	def TestGet(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp = rs.Get(key, downLoadFileName)
			resp = rs.GetIfNotModified(key, downLoadFileName, resp['hash'])
			f = open(downLoadFileName, "w")
			f.write(urllib.urlopen(resp['url']).read())
			f.close()
			flag =filecmp.cmp("rs_demo.py","Download")
			if not flag:
				print "files' contents are not same"
				return 1
			os.remove(downLoadFileName)
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		return 0


	def TestGetUnfind(self):
		client = simpleoauth2.Client()
		try:
			client.ExchangeByPassword('qboxtest', 'qboxtest123')
			rs = qboxrs.Service(client, tblName)
			resp = rs.Get('icannotfind', downLoadFileName)
			resp = rs.GetIfNotModified('icannotfind', downLoadFileName, resp['hash'])
			f = open(downLoadFileName, "w")
			f.write(urllib.urlopen(resp['url']).read())
			os.remove(downLoadFileName)
		except Exception,data:
			#print Exception,":",data
			#print traceback.print_exc()
			return 0
		return 1

	"""
	def TestBatch(self):
		client = simpleoauth2.Client()
		try:
			client.ExchangeByPassword('qboxtest', 'qboxtest123')
			rs = qboxrs.Service(client, tblName)
			resp = rs.Drop()
			resp = rs.PutAuth()
			key1 = 'file1'
			resp1 = rscli.PutFile(resp['url'], tblName, key1, '', fileName, 'CustomData', {'key': key1})
			key2 = 'file2'
			resp2 = rscli.PutFile(resp['url'], tblName, key2, '', fileName, 'CustomData', {'key': key2})
			rs.Batch('stat', key1, key2, 'icannotfind')
			rs.Batch('get', key1, key2, 'icannotfind')
			rs.Batch('delete',key1, key2)
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		resp = rs.Drop()
		return 0
	"""
	def TestPublish(self):
		rs = self.rs
		try:
			resp = rs.Drop()
			resp = rs.PutAuth()
			resp1 = rscli.PutFile(resp['url'], tblName, key, '', fileName, 'CustomData', {'key': key})
			resp = rs.Publish(config.DEMO_DOMAIN)
			url = "http://" + config.DEMO_DOMAIN  + '/' + key
			#print url
			f = open(downLoadFileName, "w")
			f.write(urllib.urlopen(url).read())
			f.close()
			if not filecmp.cmp(fileName, downLoadFileName):
				print "files' content not match"
				resp = rs.Unpublish(config.DEMO_DOMAIN)
				rs.Drop()
				return 1
			os.remove(downLoadFileName)
		except Exception,data:
			print Exception,":",data
			print traceback.print_exc()
			return 1
		try:
			resp = rs.Unpublish(config.DEMO_DOMAIN)
			url = config.DEMO_DOMAIN  + '/' + key
			f = open(downLoadFileName, "w")
			f.write(urllib.urlopen(url).read())
			f.close()
			os.remove(downLoadFileName)
		except Exception,data:
			#print Exception,":",data
			#print traceback.print_exc()
			os.remove(downLoadFileName)
			return 0
		return 1

