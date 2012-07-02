#coding=utf8

import config
from base64 import urlsafe_b64encode

class Service:
	"""
	 * QBox Resource Storage (Key-Value) Service
	 * QBox 资源存储(键值对)。基本特性为：每个账户可创建多个表，每个表包含多个键值对(Key-Value对)，Key是任意的字符串，Value是一个文件。
	"""

	def __init__(self, conn, bucket = ''):
		self.Conn = conn
		self.TableName = bucket

	def PutAuth(self):
		"""
		 * func PutAuth() => PutAuthRet
		 * 上传授权（生成一个短期有效的可匿名上传URL）
		"""
		url = config.IO_HOST + '/put-auth/'
		return self.Conn.Call(url)

	def PutAuthEx(self, expires, cbUrl):
		"""
		 * func PutAuthEx(expires, callbackUrl) => PutAuthRet
		 * 上传授权（生成一个短期有效的可匿名上传URL）
		"""
                url = config.IO_HOST + '/put-auth/' + str(expires) + '/callback/' + urlsafe_b64encode(cbUrl)
		return self.Conn.Call(url)

	def Get(self, key, attName):
		"""
		 * func Get(key string, attName string) => GetRet
		 * 下载授权（生成一个短期有效的可匿名下载URL）
		"""
		entryURI = self.TableName + ':' + key
		url = config.RS_HOST + '/get/' + urlsafe_b64encode(entryURI) + '/attName/' + urlsafe_b64encode(attName)
		return self.Conn.Call(url)

	def GetIfNotModified(self, key, attName, base):
		"""
		 * func GetIfNotModified(key string, attName string, base string) => GetRet
		 * 下载授权（生成一个短期有效的可匿名下载URL），如果服务端文件没被人修改的话（用于断点续传）
		"""
		entryURI = self.TableName + ':' + key
		url = config.RS_HOST + '/get/' + urlsafe_b64encode(entryURI) + '/attName/' + urlsafe_b64encode(attName) + '/base/' + base
		return self.Conn.Call(url)

	def Stat(self, key):
		"""
		 * func Stat(key string) => Entry
		 * 取资源属性
		"""
		entryURI = self.TableName + ':' + key
		url = config.RS_HOST + '/stat/' + urlsafe_b64encode(entryURI)
		return self.Conn.Call(url)

	def Publish(self, domain):
		"""
		 * func Publish(domain string) => Bool
		 * 将本 Table 的内容作为静态资源发布。静态资源的url为：http://domain/key
		"""
		url = config.RS_HOST + '/publish/' + urlsafe_b64encode(domain) + '/from/' + self.TableName
		return self.Conn.CallNoRet(url)

	def Unpublish(self, domain):
		"""
		 * func Unpublish(domain string) => Bool
		 * 取消发布
		"""
		url = config.RS_HOST + '/unpublish/' + urlsafe_b64encode(domain)
		return self.Conn.CallNoRet(url)

	def Delete(self, key):
		"""
		 * func Delete(key string) => Bool
		 * 删除资源
		"""
		entryURI = self.TableName + ':' + key
		url = config.RS_HOST + '/delete/' + urlsafe_b64encode(entryURI)
		return self.Conn.CallNoRet(url)

	def Drop(self):
		"""
		 * func Drop() => Bool
		 * 删除整个表（慎用！）
		"""
		url = config.RS_HOST + '/drop/' + self.TableName
		return self.Conn.CallNoRet(url)

