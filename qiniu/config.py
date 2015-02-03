# -*- coding: utf-8 -*-

RS_HOST = 'rs.qbox.me'      # 管理操作Host
IO_HOST = 'iovip.qbox.me'   # 七牛源站Host
RSF_HOST = 'rsf.qbox.me'    # 列举操作Host
API_HOST = 'api.qiniu.com'  # 数据处理操作Host

UPAUTO_HOST = 'up.qiniu.com'        # 默认上传Host
UPDX_HOST = 'updx.qiniu.com'        # 电信上传Host
UPLT_HOST = 'uplt.qiniu.com'        # 移动上传Host
UPBACKUP_HOST = 'upload.qiniu.com'  # 备用上传Host

_config = {
    'default_up_host': UPAUTO_HOST,  # 设置为默认上传Host
    'connection_timeout': 30,        # 链接超时为时间为30s
    'connection_retries': 3,         # 链接重试次数为3次
    'connection_pool': 10,           # 链接池个数为10

}
_BLOCK_SIZE = 1024 * 1024 * 4  # 断点续上传分块大小，该参数为接口规格，暂不支持修改


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
