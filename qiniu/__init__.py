# -*- coding: utf-8 -*-
'''
Qiniu Resource Storage SDK for Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For detailed document, please see:
<http://developer.qiniu.com>
'''

# flake8: noqa

__version__ = '7.1.1'

from .auth import Auth, QiniuMacAuth

from .config import set_default
from .zone import Zone

from .services.storage.bucket import BucketManager, build_batch_copy, build_batch_rename, build_batch_move, \
    build_batch_stat, build_batch_delete
from .services.storage.uploader import put_data, put_file, put_stream
from .services.cdn.manager import CdnManager, create_timestamp_anti_leech_url
from .services.processing.pfop import PersistentFop
from .services.processing.cmd import build_op, pipe_cmd, op_save
from .services.compute.app import AccountClient
from .services.compute.qcos_api import QcosClient

from .utils import urlsafe_base64_encode, urlsafe_base64_decode, etag, entry
