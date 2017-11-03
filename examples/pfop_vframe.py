# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth, PersistentFop, urlsafe_base64_encode

# 对已经上传到七牛的视频发起异步转码操作
access_key = 'Access_Key'
secret_key = 'Secret_Key'
q = Auth(access_key, secret_key)

# 要转码的文件所在的空间和文件名。
bucket = 'Bucket_Name'
key = '1.mp4'

# 转码是使用的队列名称。
pipeline = 'pipeline_name'

# 要进行视频截图操作。
fops = 'vframe/jpg/offset/1/w/480/h/360/rotate/90'

# 可以对转码后的文件进行使用saveas参数自定义命名，当然也可以不指定文件会默认命名并保存在当前空间
saveas_key = urlsafe_base64_encode('目标Bucket_Name:自定义文件key')
fops = fops+'|saveas/'+saveas_key

pfop = PersistentFop(q, bucket, pipeline)
ops = []
ops.append(fops)
ret, info = pfop.execute(key, ops, 1)
print(info)
assert ret['persistentId'] is not None