# -*- coding: utf-8 -*-

RS_HOST = 'rs.qbox.me'
IO_HOST = 'iovip.qbox.me'
RSF_HOST = 'rsf.qbox.me'
API_HOST = 'api.qiniu.com'

UPAUTO_HOST = 'up.qiniu.com'
UPDX_HOST = 'updx.qiniu.com'
UPLT_HOST = 'uplt.qiniu.com'
UPBACKUP_HOST = 'upload.qiniu.com'

_config = {
    'default_up_host': UPAUTO_HOST,
    'connection_timeout': 30,
    'connection_retries': 3,
    'connection_pool': 10,

}
_BLOCK_SIZE = 1024 * 1024 * 4


def get_default(key):
    return _config[key]


def set_default(
        default_up_host=None, connection_retries=None, connection_pool=None, connection_timeout=None):
    if default_up_host:
        _config['default_up_host'] = default_up_host
    if connection_retries:
        _config['connection_retries'] = connection_retries
    if connection_pool:
        _config['connection_pool'] = connection_pool
    if connection_timeout:
        _config['connection_timeout'] = connection_timeout
