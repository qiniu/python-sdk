# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import Auth, PersistentFop, build_op, op_save, urlsafe_base64_encode

#对已经上传到七牛的视频发起异步转码操作 
access_key = 'Access_Key'
secret_key = 'Secret_Key'
q = Auth(access_key, secret_key)

#要转码的文件所在的空间和文件名。
bucket = 'Bucket_Name'
key = '1.mp4'

#转码是使用的队列名称。
pipeline = 'mpsdemo'

#需要添加水印的图片UrlSafeBase64,可以参考http://developer.qiniu.com/code/v6/api/dora-api/av/video-watermark.html
base64URL = urlsafe_base64_encode('http://developer.qiniu.com/resource/logo-2.jpg');

#视频水印参数
fops = 'avthumb/mp4/'+base64URL

#可以对转码后的文件进行使用saveas参数自定义命名，当然也可以不指定文件会默认命名并保存在当前空间
saveas_key = urlsafe_base64_encode('目标Bucket_Name:自定义文件key')
fops = fops+'|saveas/'+saveas_key

pfop = PersistentFop(q, bucket, pipeline)
ops = []
ops.append(fops)
ret, info = pfop.execute(key, ops, 1)
print(info)
assert ret['persistentId'] 