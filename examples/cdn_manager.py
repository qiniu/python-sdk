# -*- coding: utf-8 -*-
import qiniu
from qiniu import CdnManager
from qiniu import create_timestamp_anti_leech_url
import time


# 演示函数调用结果
def print_result(result):
    if result[0] is not None:
        print(type(result[0]))
        print(result[0])

    print(type(result[1]))
    print(result[1])


# 账户ak，sk
access_key = '...'
secret_key = '...'

auth = qiniu.Auth(access_key=access_key, secret_key=secret_key)
cdn_manager = CdnManager(auth)

urls = [
    'http://if-pbl.qiniudn.com/qiniu.jpg',
    'http://if-pbl.qiniudn.com/qiniu2.jpg'
]

# 注意链接最后的斜杠表示目录
dirs = [
    'http://if-pbl.qiniudn.com/test1/',
    'http://if-pbl.qiniudn.com/test2/'
]
"""刷新文件，目录"""

# 刷新链接
print('刷新文件')
refresh_url_result = cdn_manager.refresh_urls(urls)
print_result(refresh_url_result)

# 刷新目录需要联系七牛技术支持开通权限
print('刷新目录')
refresh_dir_result = cdn_manager.refresh_dirs(dirs)
print_result(refresh_dir_result)

# 同时刷新文件和目录
print('刷新文件和目录')
refresh_all_result = cdn_manager.refresh_urls_and_dirs(urls, dirs)
print_result(refresh_all_result)

"""预取文件"""

# 预取文件链接
print('预取文件链接')
prefetch_url_result = cdn_manager.prefetch_urls(urls)
print_result(prefetch_url_result)

"""获取带宽和流量数据"""

domains = ['if-pbl.qiniudn.com', 'qdisk.qiniudn.com']

start_date = '2017-01-01'
end_date = '2017-01-02'

# 5min or hour or day
granularity = 'day'

# 获取带宽数据
print('获取带宽数据')
bandwidth_data = cdn_manager.get_bandwidth_data(domains, start_date, end_date, granularity)
print_result(bandwidth_data)

# 获取流量数据
print('获取流量数据')
flux_data = cdn_manager.get_flux_data(domains, start_date, end_date, granularity)
print_result(flux_data)

"""获取日志文件下载地址列表"""
# 获取日志列表
print('获取日志列表')
log_date = '2017-01-01'
log_data = cdn_manager.get_log_list_data(domains, log_date)
print_result(log_data)

"""构建时间戳防盗链"""

# 构建时间戳防盗链
print('构建时间戳防盗链')

# 时间戳防盗链密钥，后台获取
encrypt_key = 'xxx'

# 原始文件名，必须是utf8编码
test_file_name1 = '基本概括.mp4'
test_file_name2 = '2017/01/07/test.png'

# 查询参数列表
query_string_dict = {
    'name': '七牛',
    'year': 2017,
    '年龄': 28,
}

# 带访问协议的域名
host = 'http://video.example.com'

# unix时间戳
deadline = int(time.time()) + 3600

# 带查询参数，中文文件名
signed_url1 = create_timestamp_anti_leech_url(host, test_file_name1, query_string_dict, encrypt_key, deadline)
print(signed_url1)

# 带查询参数，英文文件名
signed_url2 = create_timestamp_anti_leech_url(host, test_file_name2, query_string_dict, encrypt_key, deadline)
print(signed_url2)

# 不带查询参数，中文文件名
signed_url3 = create_timestamp_anti_leech_url(host, test_file_name1, None, encrypt_key, deadline)
print(signed_url3)

# 不带查询参数，英文文件名
signed_url4 = create_timestamp_anti_leech_url(host, test_file_name2, None, encrypt_key, deadline)
print(signed_url4)
