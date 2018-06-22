# -*- coding: utf-8 -*-
# flake8: noqa
from qiniu import QiniuMacAuth, video_pulp

# 对已经上传到七牛的视频发起异步转码操作
access_key = 'Access_Key'
secret_key = 'Secret_Key'
q = QiniuMacAuth(access_key, secret_key)


url = ''  # 要鉴别的视频地址
video_id = ''  # 视频的唯一ID


ret, info = video_pulp(q, video_id, url)

print(info)
assert 'pulp' in ret
