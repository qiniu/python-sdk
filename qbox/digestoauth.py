# -*- encoding: utf-8 -*-

"""A simple client library to work with Digest Oauth APIs."""

__author__ = 'stevenle08@gmail.com (Steven Le); xushiwei@qbox.net'


import config
import httplib2
import hmac
import urllib
from urlparse import urlparse
from hashlib import sha1
from base64 import urlsafe_b64encode

try:
  import json
except ImportError:
  import simplejson as json


class Error(Exception):
  pass


class Client(object):

  def Call(self, url):
    headers = {}

    digest = self.CheckSum(url)
    token = "%s:%s" % (config.ACCESS_KEY,digest)
    headers['Authorization'] = 'QBox %s' % (token)
    resp, content = httplib2.Http('').request(url, 'POST', '', headers=headers)

    code = resp['status']
    if code != '200':
      raise Error('DigestOauthRequest.Call failed. Error was: %s %s' % (code, content))
    if len(content) != 0:
      return json.loads(content)
    return True

  def CallNoRet(self, url):
    headers = {}
    digest = self.CheckSum(url)
    token = "%s:%s" % (config.ACCESS_KEY,digest)
    headers['Authorization'] = 'QBox %s' % (token)
    resp, content = httplib2.Http('').request(url, 'POST', '', headers=headers)

    code = resp['status']
    if code != '200':
      raise Error('DigestOauthRequest.Call failed. Error was: %s %s' % (code, content))
    return True

  def CheckSum(self, url, params=None):
    parsedurl = urlparse(url)
    query = parsedurl.query
    path = parsedurl.path
    data = path
    if query != "":
      data = ''.join([data,'?',query])
    data = ''.join([data,"\n"])

    if params != None:
      data = ''.join([data,params])

    hashed = hmac.new(config.SECRET_KEY,data,sha1)
    return urlsafe_b64encode(hashed.digest())

  def CallWithForm(self, url, params):
    headers = {}

    msg = urllib.urlencode(params)

    digest = self.CheckSum(url, msg)
    token = "%s:%s" % (config.ACCESS_KEY,digest)

    headers['Authorization'] = 'QBox %s' % (token)
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    resp, content = httplib2.Http('').request(url, 'POST', msg, headers=headers)

    code = resp['status']
    if code != '200':
      raise Error('DigestOauthRequest.Call failed. Error was: %s %s' % (code, content))

    if len(content) != 0:
      return json.loads(content)
    return True
