# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth, PersistentFop, urlsafe_base64_encode

# 对已经上传到七牛的视频发起异步转码操作
access_key = '...'
secret_key = '...'
q = Auth(access_key, secret_key)

# 要转码的文件所在的空间和文件名。
bucket_name = 'Bucket_Name'
key = '1.mp4'

# 转码是使用的队列名称。
pipeline = 'your_pipeline'

# 要进行转码的转码操作，下面是一个例子。
fops = 'avthumb/mp4/s/640x360/vb/1.25m'

# 可以对转码后的文件进行使用saveas参数自定义命名，当然也可以不指定文件会默认命名并保存在当前空间
saveas_key = urlsafe_base64_encode('目标Bucket_Name:自定义文件key')
fops = fops+'|saveas/'+saveas_key
ops = []
pfop = PersistentFop(q, bucket_name, pipeline)

ops.append(fops)
ret, info = pfop.execute(key, ops, 1)
print(info)
assert ret['persistentId'] is not None
