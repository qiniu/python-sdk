# -*- coding: utf-8 -*-


from qiniu import Auth
from qiniu import put_data,etag
import qiniu.config

access_key = 'oPQDbCnHhXjZtGZk6ysNYDMrcs7a8Puy_e0mcaL_'
secret_key = 'DzQHHAizEpsr3LqiIfjF8-p2cBi406nR44CYasBx'
bucket_name = 'a123'

q = Auth(access_key, secret_key)

# 上传本地文件


key = '0222'
data='hello bubby!'
mime_type = None #可以设定上传 mime_type 类型
params = {'x:a': 'a'}

policy={'fsizeMin':100000}

token = q.upload_token('a123', key, 3600, policy)

ret, info = put_data(token, key, data, check_crc=True)
#assert
print(info)
