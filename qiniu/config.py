# -*- coding: utf-8 -*-
RS_HOST = 'http://rs.qiniu.com'  # 管理操作Host
RSF_HOST = 'http://rsf.qbox.me'  # 列举操作Host
API_HOST = 'http://api.qiniuapi.com'  # 数据处理操作Host
UC_HOST = 'https://uc.qbox.me'  # 获取空间信息Host
QUERY_REGION_HOST = 'https://kodo-config.qiniuapi.com'
QUERY_REGION_BACKUP_HOSTS = [
    'uc.qbox.me',
    'api.qiniu.com'
]

_BLOCK_SIZE = 1024 * 1024 * 4  # 断点续传分块大小，该参数为接口规格，暂不支持修改

_config = {
    'default_zone': None,
    'default_rs_host': RS_HOST,
    'default_rsf_host': RSF_HOST,
    'default_api_host': API_HOST,
    'default_uc_host': UC_HOST,
    'default_query_region_host': QUERY_REGION_HOST,
    'default_query_region_backup_hosts': QUERY_REGION_BACKUP_HOSTS,
    'default_backup_hosts_retry_times': 3,  # 仅控制旧 Region 查询 Hosts 的重试次数
    'connection_timeout': 30,  # 链接超时为时间为30s
    'connection_retries': 3,  # 链接重试次数为3次
    'connection_pool': 10,  # 链接池个数为10
    'default_upload_threshold': 2 * _BLOCK_SIZE  # put_file上传方式的临界默认值
}

_is_customized_default = {
    'default_zone': False,
    'default_rs_host': False,
    'default_rsf_host': False,
    'default_api_host': False,
    'default_uc_host': False,
    'default_query_region_host': False,
    'default_query_region_backup_hosts': False,
    'default_backup_hosts_retry_times': False,
    'connection_timeout': False,
    'connection_retries': False,
    'connection_pool': False,
    'default_upload_threshold': False
}


def is_customized_default(key):
    return _is_customized_default[key]


def get_default(key):
    if key == 'default_zone' and not _is_customized_default[key]:
        # prevent circle import
        from .region import Region
        return Region()
    return _config[key]


def set_default(
        default_zone=None, connection_retries=None, connection_pool=None,
        connection_timeout=None, default_rs_host=None, default_uc_host=None,
        default_rsf_host=None, default_api_host=None, default_upload_threshold=None,
        default_query_region_host=None, default_query_region_backup_hosts=None,
        default_backup_hosts_retry_times=None):
    if default_zone:
        _config['default_zone'] = default_zone
        _is_customized_default['default_zone'] = True
    if default_rs_host:
        _config['default_rs_host'] = default_rs_host
        _is_customized_default['default_rs_host'] = True
    if default_rsf_host:
        _config['default_rsf_host'] = default_rsf_host
        _is_customized_default['default_rsf_host'] = True
    if default_api_host:
        _config['default_api_host'] = default_api_host
        _is_customized_default['default_api_host'] = True
    if default_uc_host:
        _config['default_uc_host'] = default_uc_host
        _is_customized_default['default_uc_host'] = True
        _config['default_query_region_host'] = default_uc_host
        _is_customized_default['default_query_region_host'] = True
        _config['default_query_region_backup_hosts'] = []
        _is_customized_default['default_query_region_backup_hosts'] = True
    if default_query_region_host:
        _config['default_query_region_host'] = default_query_region_host
        _is_customized_default['default_query_region_host'] = True
        _config['default_query_region_backup_hosts'] = []
        _is_customized_default['default_query_region_backup_hosts'] = True
    if default_query_region_backup_hosts:
        _config['default_query_region_backup_hosts'] = default_query_region_backup_hosts
        _is_customized_default['default_query_region_backup_hosts'] = True
    if default_backup_hosts_retry_times:
        _config['default_backup_hosts_retry_times'] = default_backup_hosts_retry_times
        _is_customized_default['default_backup_hosts_retry_times'] = True
    if connection_retries:
        _config['connection_retries'] = connection_retries
        _is_customized_default['connection_retries'] = True
    if connection_pool:
        _config['connection_pool'] = connection_pool
        _is_customized_default['connection_pool'] = True
    if connection_timeout:
        _config['connection_timeout'] = connection_timeout
        _is_customized_default['connection_timeout'] = True
    if default_upload_threshold:
        _config['default_upload_threshold'] = default_upload_threshold
        _is_customized_default['default_upload_threshold'] = True
