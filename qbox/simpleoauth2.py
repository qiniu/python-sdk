"""A simple client library to work with OAuth 2.0 APIs."""

__author__ = 'stevenle08@gmail.com (Steven Le); xushiwei@qbox.net; why404@gmail.com'

import config
import httplib2

from string import split
from urllib import urlencode
from urlparse import urlparse
from urlparse import urlunparse

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

    def __init__(self, auth_url=config.AUTHORIZATION_ENDPOINT, token_url=config.TOKEN_ENDPOINT, client_id=config.CLIENT_ID, client_secret=config.CLIENT_SECRET):
        self.auth_url = auth_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret

        self.cached_host = {}

    def CreateAuthUrl(self, scope, redirect_uri, state=None):
        """Creates a authorization URL.

        Args:
            scope: A scope or list of scopes identifying the service to be accessed.
            redirect_uri: The URL on your site that will handle OAuth responses after the user takes an action on the dialog.
            state: A string used to maintain state between the request and redirect.
                This value will be appended to the redirect_uri after the user takes an action on the OAuth dialog.

        Returns:
            A URL to that can be used to redirect users to authorize access to a service.
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

        return '%s?%s' % (self.auth_url, urlencode(params))

    def Exchange(self, code, redirect_uri):
        """Requests an access token using an authorization code.

        Args:
            code: Authorization code provided by user from the authorization URL.

        Returns:
            A dict representing a token, including an access_token and a refresh_token.
        """
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }
        body = urlencode(params)
        resp, content = self.ExecuteRequestSafely(self.token_url, body)

        if resp['status'] != '200':
            raise Error('Could not fetch access token. Error was: %s %s' % (resp['status'], content))
        self.token = json.loads(content)
        return self.token

    def ExchangeByPassword(self, user, passwd):
        """Requests an access token using user name & password.

        Args:
            user: user name.
            passwd: passowrd.

        Returns:
            A dict representing a token, including an access_token and a refresh_token.
        """
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': user,
            'password': passwd,
            'grant_type': 'password',
        }
        body = urlencode(params)
        resp, content = self.ExecuteRequestSafely(self.token_url, body)
        if resp['status'] != '200':
            raise Error('Could not fetch access token. Error was: %s %s' % (resp['status'], content))
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
        body = urlencode(params)
        resp, content = self.ExecuteRequestSafely(self.token_url, body)
        if resp['status'] != '200':
            raise Error('Could not fetch access token. Error was: %s %s' % (resp['status'], content))
        self.token = json.loads(content)
        return self.token

    def Call(self, url, _retries=0, _max_retries=1):
        headers = {}
        headers['Authorization'] = 'Bearer %s' % self.token['access_token']
        resp, content = self.ExecuteRequestSafely(url, "", headers=headers)

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
        resp, content = self.ExecuteRequestSafely(url, "", headers=headers)

        code = resp['status']
        if code == '401' and _retries < _max_retries:
            self.token = self.ExchangeByRefreshToken(self.token['refresh_token'])
            return self.CallNoRet(url, _retries + 1, _max_retries)
        if code != '200':
            raise Error('OAuthRequest.Call failed. Error was: %s %s' % (code, content))
        return True

    def ExecuteRequestSafely(self, url, body="", headers={}, method="POST", _retries=0, _max_retries=3):
        try:
            parts = list(urlparse(url))
            netloc = parts[1]
            netloc_parts = split(netloc, ".")

            if len(netloc_parts) > 2:
                n = netloc_parts[0][-1]
                if n.isdigit() == True:
                    n = int(n)
                    prefix = netloc_parts[0][0:-1]
                else:
                    n = 1
                    prefix = netloc_parts[0]

                if self.cached_host.has_key(prefix):
                    cached_parts = parts[:]
                    cached_parts[1] = self.cached_host[prefix]
                    url = urlunparse(cached_parts)

            resp, content = httplib2.Http().request(url, method, body=body, headers=headers)

            if _retries > 0 and _retries < _max_retries:
                self.cached_host[prefix] = netloc

            return resp, content

        except httplib2.ServerNotFoundError:
            if _retries < _max_retries:
                n = 1 if n >= _max_retries else n + 1
                new_prefix = prefix if n == 1 else prefix + ("%d" % n)

                new_netloc_parts = netloc_parts[:]
                new_netloc_parts[0] = new_prefix
                new_netloc = ".".join(new_netloc_parts)
                new_parts = parts[:]
                new_parts[1] = new_netloc
                newURL = urlunparse(new_parts)

                return self.ExecuteRequestSafely(newURL, body, headers, method, _retries+1, _max_retries)
            else:
                return {}, ""
