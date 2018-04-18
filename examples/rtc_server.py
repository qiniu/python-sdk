#-*- coding: utf-8 -*-
#flake8: noqa
# from qiniu import Auth
# from qiniu import BucketManager

# access_key = '...'
# secret_key = '...'
#
# q = Auth(access_key, secret_key)
# bucket = BucketManager(q)
#
# bucket_name = 'Bucket_Name'
# # 前缀
# prefix = None
# # 列举条目
# limit = 10
# # 列举出除'/'的所有文件以及以'/'为分隔的所有前缀
# delimiter = None
# # 标记
# marker = None
#
# ret, eof, info = bucket.list(bucket_name, prefix, marker, limit, delimiter)
#
# print(info)
#
# assert len(ret.get('items')) is not None

import sys
sys.path.append('/Users/yunchuanzhang/python3/lib/python3.5/site-packages/python-sdk/qiniu')

from qiniu import QiniuMacAuth
from qiniu import RtcServer, RtcRoomToken


# UID 1380668373  PILI—VDN内部测试账号
access_key = 'DXFtikq1YuDT_WMUntOpzpWPm2UZVtEnYvN3-CUD'
secret_key = 'F397hzMohpORVZ-bBbb-IVbpdWlI4SWu8sWq78v3'

q = QiniuMacAuth(access_key, secret_key )

rtc = RtcServer(q)


#print ( rtc.GetApp() )
#print ('\n\n\n')
#
#
# create_data={
# 	"hub": 'python_test_hub',
# 	"title": 'python_test_app',
# 	# "maxUsers": MaxUsers,
# 	# "noAutoCloseRoom": NoAutoCloseRoom,
# 	# "noAutoCreateRoom": NoAutoCreateRoom,
# 	# "noAutoKickUser": NoAutoKickUser
# }
# print ( rtc.CreateApp(create_data) )
# print ('\n\n\n')
#
#
# print ( rtc.DeleteApp('desls83s2') )
# print ('\n\n\n')
#
#
# update_data={
#     "hub": "python_new_hub",
#     "title": "python_new_app",
#     # "maxUsers": <MaxUsers>,
#     # "noAutoCloseRoom": <NoAutoCloseRoom>,
#     # "noAutoCreateRoom": <NoAutoCreateRoom>,
#     # "noAutoKickUser": <NoAutoKickUser>,
#     # "mergePublishRtmp": {
#     #     "enable": <Enable>,
#     #     "audioOnly": <AudioOnly>,
#     #     "height": <OutputHeight>,
#     #     "width": <OutputHeight>,
#     #     "fps": <OutputFps>,
#     #     "kbps": <OutputKbps>,
#     #     "url": "<URL>",
#     #     "streamTitle": "<StreamTitle>"
#     # }
# }
# print ( rtc.UpdateApp('desmfnkw5', update_data) )
# print ('\n\n\n')
#

# print ( rtc.ListUser( 'd7rqwfxqd','test' ) )
# print ('\n\n\n')
#
# print ( rtc.KickUser( 'd7rqwfxqd', 'test' ,'test' ) )
# print ('\n\n\n')
#
# print ( rtc.ListActiveRoom( 'd7rqwfxqd' ) )
# print ('\n\n\n')

# roomAccess = {
# 		    "appId": "d7rqwfxqd" ,
# 		    "roomName": "RoomName" ,
# 		    "userId": "UserID" ,
# 		    "expireAt": "1524056400" ,
# 		    "permission": "user"
# 		}
# print (RtcRoomToken ( access_key, secret_key,  roomAccess ) )
# print ('\n\n\n')


# access_key='gwd_gV4gPKZZsmEOvAuNU1AcumicmuHooTfu64q5'
# secret_key='9G4isTkVuj5ITPqH1ajhljJMTc2k4m-hZh5r5ZsK'
#
# roomAccess = {
# 		    "appId": "desobxqpx" ,
# 		    "roomName": "lfxl" ,
# 		    "userId": "1111" ,
# 		    "expireAt": "" ,
# 		    "permission": ""
# 		}
# print (RtcRoomToken ( access_key, secret_key,  roomAccess ) )
#









