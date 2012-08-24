#coding=utf8

import config

class Service:
	"""
	 * End-user Settings Service
	 * 终端用户配置项服务
	"""

	def __init__(self, conn):
		self.Conn = conn

	def GetWatermark(self, customer):
		url = config.EU_HOST+"/wmget"
		params = {}
		params["customer"] = customer
		return self.Conn.CallWithForm(url, params)

	def SetWatermark(self, customer, tpl):
		url = config.EU_HOST+"/wmset"
		tpl["customer"] = customer
		ret = self.Conn.CallWithForm(url, tpl)
		tpl.pop("customer")
		return ret
