# -*- encoding: utf-8 -*-

"""A simple client library to work with OAuth 2.0 APIs."""

__author__ = 'stevenle08@gmail.com (Steven Le); xushiwei@qbox.net'


import config
import urllib
import httplib2
try:
  import json
except ImportError:
  import simplejson as json


class Error(Exception):
  pass


class Client(object):
  """The base class for OAuth 2.0 clients.

  Attributes:
    auth_url: The OAuth 2.0 endpoint to redirect users to to authorize access.
    token_url: The OAuth 2.0 endpoint to request and refresh tokens.
    client_id: The client ID issued by the OAuth 2.0 service.
    client_secret: The client secret issued by the OAuth 2.0 service.
    token: OAuth 2.0 token.
  """

  def __init__(self, auth_url=config.AUTHORIZATION_ENDPOINT, token_url=config.TOKEN_ENDPOINT, client_id="a75604760c4da4caaa456c0c5895c061c3065c5a", client_secret="75df554a39f58accb7eb293b550fa59618674b7d"):
    self.auth_url = auth_url
    self.token_url = token_url
    self.client_id = client_id
    self.client_secret = client_secret

  def CreateAuthUrl(self, scope, redirect_uri, state=None):
    """Creates a authorization URL.

    Args:
      scope: A scope or list of scopes identifying the service to be accessed.
      redirect_uri: The URL on your site that will handle OAuth responses after
          the user takes an action on the dialog.
      state: A string used to maintain state between the request and redirect.
          This value will be appended to the redirect_uri after the user takes
          an action on the OAuth dialog.
    Returns:
      A URL to that can be used to redirect users to authorize access to a
      service.
    """
    if hasattr(scope, '__iter__'):
      # Multiple scopes.
      scope = ' '.join(scope)

    params = {
        'client_id': self.client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'response_type': 'code',
    }
    if state:
      params['state'] = state

    return '%s?%s' % (self.auth_url, urllib.urlencode(params))

  def Exchange(self, code, redirect_uri):
    """Requests an access token using an authorization code.

    Args:
      code: Authorization code provided by user from the authorization URL.
    Returns:
      A dict representing a token, including an access_token and a
      refresh_token.
    """
    params = {
        'client_id': self.client_id,
        'client_secret': self.client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    body = urllib.urlencode(params)
    resp, content = httplib2.Http('').request(self.token_url, 'POST', body)
    if resp['status'] != '200':
      raise Error('Could not fetch access token. Error was: %s %s'
                       % (resp['status'], content))
    self.token = json.loads(content)
    return self.token

  def ExchangeByPassword(self, user, passwd):
    """Requests an access token using user name & password.

    Args:
      user: user name.
      passwd: passowrd.
    Returns:
      A dict representing a token, including an access_token and a
      refresh_token.
    """
    params = {
        'client_id': self.client_id,
        'client_secret': self.client_secret,
        'username': user,
        'password': passwd,
        'grant_type': 'password',
    }
    body = urllib.urlencode(params)
    resp, content = httplib2.Http('').request(self.token_url, 'POST', body)
    if resp['status'] != '200':
      raise Error('Could not fetch access token. Error was: %s %s'
                       % (resp['status'], content))
    self.token = json.loads(content)
    return self.token

  def ExchangeByRefreshToken(self, refresh_token):
    """Refreshes an access token.

    Args:
      refresh_token: The refresh token.
    Returns:
      A dict representing a refreshed token.
    """
    params = {
        'client_id': self.client_id,
        'client_secret': self.client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    body = urllib.urlencode(params)
    resp, content = httplib2.Http('').request(self.token_url, 'POST', body)
    if resp['status'] != '200':
      raise Error('Could not fetch access token. Error was: %s %s'
                       % (resp['status'], content))
    self.token = json.loads(content)
    return self.token

  def Call(self, url, _retries=0, _max_retries=1):
    headers = {}
    headers['Authorization'] = 'Bearer %s' % self.token['access_token']
    resp, content = httplib2.Http('').request(url, 'POST', '', headers=headers)

    code = resp['status']
    if code == '401' and _retries < _max_retries:
      self.token = self.ExchangeByRefreshToken(self.token['refresh_token'])
      return self.Call(url, _retries + 1, _max_retries)
    if code != '200':
      raise Error('OAuthRequest.Call failed. Error was: %s %s' % (code, content))
    return json.loads(content)

  def CallNoRet(self, url, _retries=0, _max_retries=1):
    headers = {}
    headers['Authorization'] = 'Bearer %s' % self.token['access_token']
    resp, content = httplib2.Http('').request(url, 'POST', '', headers=headers)

    code = resp['status']
    if code == '401' and _retries < _max_retries:
      self.token = self.ExchangeByRefreshToken(self.token['refresh_token'])
      return self.CallNoRet(url, _retries + 1, _max_retries)
    if code != '200':
      raise Error('OAuthRequest.Call failed. Error was: %s %s' % (code, content))
    return True

