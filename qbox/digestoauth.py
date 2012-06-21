"""A simple client library to work with Digest Oauth APIs."""

__author__ = 'stevenle08@gmail.com (Steven Le); xushiwei@qbox.net'


import config
import httplib2
import hmac
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

  def Call(self, url, _retries=0, _max_retries=1):
    headers = {}

    digest = self.CheckSum(url)
    token = "%s:%s" % (config.KEY,digest)
    headers['Authorization'] = 'QBox %s' % (token)
    resp, content = httplib2.Http('').request(url, 'POST', '', headers=headers)
    

    code = resp['status']
    if code != '200':
      raise Error('DigestOauthRequest.Call failed. Error was: %s %s' % (code, content))
    return json.loads(content)

  def CallNoRet(self, url, _retries=0, _max_retries=1):
    headers = {}
    digest = self.CheckSum(url)
    token = "%s:%s" % (config.KEY,digest)
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
      pass
    hashed = hmac.new(config.SECRET,data,sha1)
    return urlsafe_b64encode(hashed.digest()) 
