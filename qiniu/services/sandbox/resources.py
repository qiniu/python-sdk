# -*- coding: utf-8 -*-


class GitRepositoryResource(object):
    def __init__(self, url, mount_path, authorization_token=None,
                 repository_type='github_repository'):
        self.url = url
        self.mount_path = mount_path
        self.authorization_token = authorization_token
        self.repository_type = repository_type

    def to_dict(self):
        data = {
            'type': self.repository_type,
            'url': self.url,
            'mount_path': self.mount_path,
        }
        if self.authorization_token is not None:
            data['authorization_token'] = self.authorization_token
        return data


class KodoResource(object):
    def __init__(self, bucket, mount_path, prefix=None, read_only=None,
                 access_key=None, secret_key=None):
        self.bucket = bucket
        self.mount_path = mount_path
        self.prefix = prefix
        self.read_only = read_only
        self.access_key = access_key
        self.secret_key = secret_key

    def to_dict(self):
        data = {
            'type': 'kodo',
            'bucket': self.bucket,
            'mount_path': self.mount_path,
        }
        if self.prefix is not None:
            data['prefix'] = self.prefix
        if self.read_only is not None:
            data['read_only'] = self.read_only
        if (self.access_key is None) != (self.secret_key is None):
            raise ValueError('access_key and secret_key must be provided together')
        if self.access_key is not None:
            if not self.access_key or not self.secret_key:
                raise ValueError('access_key and secret_key must not be empty')
            data['access_key'] = self.access_key
            data['secret_key'] = self.secret_key
        return data
