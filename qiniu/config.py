# -*- coding: utf-8 -*-

RS_HOST = 'rs.qbox.me'      # 管理操作Host
IO_HOST = 'iovip.qbox.me'   # 七牛源站Host
RSF_HOST = 'rsf.qbox.me'    # 列举操作Host
API_HOST = 'api.qiniu.com'  # 数据处理操作Host

_BLOCK_SIZE = 1024 * 1024 * 4  # 断点续上传分块大小，该参数为接口规格，暂不支持修改


class Zone(object):
    """七牛上传区域类

    该类主要内容上传区域地址。

    Attributes:
        up_host: 首选上传地址
        up_host_backup: 备用上传地址
    """
    def __init__(self, up_host, up_host_backup):
        """初始化Zone类"""
        self.up_host, self.up_host_backup = up_host, up_host_backup


zone0 = Zone('up.qiniu.com', 'upload.qiniu.com')
zone1 = Zone('up-z1.qiniu.com', 'upload-z1.qiniu.com')

_config = {
    'default_up_host': zone0.up_host,  # 设置为默认上传Host
    'default_up_host_backup': zone0.up_host_backup,
    'default_rs_host': RS_HOST,
    'default_io_host': IO_HOST,
    'default_rsf_host': RSF_HOST,
    'default_api_host': API_HOST,
    'connection_timeout': 30,        # 链接超时为时间为30s
    'connection_retries': 3,         # 链接重试次数为3次
    'connection_pool': 10,           # 链接池个数为10
}


def get_default(key):
    return _config[key]


def set_default(
        default_zone=None, connection_retries=None, connection_pool=None,
        connection_timeout=None, default_rs_host=None, default_io_host=None,
        default_rsf_host=None, default_api_host=None):
    if default_zone:
        _config['default_up_host'] = default_zone.up_host
        _config['default_up_host_backup'] = default_zone.up_host_backup
    if default_rs_host:
        _config['default_rs_host'] = default_rs_host
    if default_io_host:
        _config['default_io_host'] = default_io_host
    if default_rsf_host:
        _config['default_rsf_host'] = default_rsf_host
    if default_api_host:
        _config['default_api_host'] = default_api_host
    if connection_retries:
        _config['connection_retries'] = connection_retries
    if connection_pool:
        _config['connection_pool'] = connection_pool
    if connection_timeout:
        _config['connection_timeout'] = connection_timeout
