import time
import config
import hmac
from hashlib import sha1
from base64 import urlsafe_b64encode

try:
  import json
except ImportError:
  import simplejson as json

class Error(Exception):
  pass

class UploadToken(object):
    def __init__(self, scope = None, expires_in = 3600, callback_url = None, return_url = None):
        self.opts = {
            'scope':scope,
            'expires_in':expires_in,
            'callback_url':callback_url,
            'return_url':return_url
        }

    def set(self, key, val):
        self.opts[key] = val

    def get(self, key):
        val = ""
        if self.opts.has_key(key):
            val = self.opts[key]
        return val

    def generate_signature(self):
        params = {"scope": self.get("scope"), "deadline": time.time()+self.get("expires_in")}
        callback_url = self.get("callback_url")
        if (callback_url != ""):
            params["callbackUrl"] = callback_url
        return_url = self.get("return_url")
        if (return_url != ""):
            params["returnUrl"] = return_url
        return urlsafe_b64encode(json.dumps(params))

    def generate_encoded_digest(self, signature):
        hashed = hmac.new(config.SECRET_KEY, signature, sha1)
        return urlsafe_b64encode(hashed.digest())

    def generate_token(self):
        signature = self.generate_signature()
        encoded_digest = self.generate_encoded_digest(signature)
        return "%s:%s:%s" % (config.ACCESS_KEY, encoded_digest, signature)

