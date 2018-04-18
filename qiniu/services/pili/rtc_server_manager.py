# -*- coding: utf-8 -*-
from qiniu import http
import json, hashlib, hmac, base64


class RtcServer(object):
	"""

	"""
	def __init__(self, auth):
		self.auth = auth
		self.host = 'http://rtc.qiniuapi.com'

	def CreateApp(self,data):
		"""
		Host rtc.qiniuapi.com
		POST /v3/apps
		Authorization: qiniu mac
		Content-Type: application/json

		{
	        "hub": "<Hub>",
	        "title": "<Title>",
	        "maxUsers": <MaxUsers>,
	        "noAutoCloseRoom": <NoAutoCloseRoom>,
	        "noAutoCreateRoom": <NoAutoCreateRoom>,
	        "noAutoKickUser": <NoAutoKickUser>
		}

		:param appid:
			Hub: 绑定的直播 hub，可选，使用此 hub 的资源进行推流等业务功能，hub 与 app 必须属于同一个七牛账户。

			Title: app 的名称，可选，注意，Title 不是唯一标识，重复 create 动作将生成多个 app。

			MaxUsers: int 类型，可选，连麦房间支持的最大在线人数。

			NoAutoCloseRoom: bool 类型，可选，禁止自动关闭房间。默认为 false ，即用户退出房间后，房间会被主动清理释放。

			NoAutoCreateRoom: bool 类型，可选，禁止自动创建房间。默认为 false ，即不需要主动调用接口创建即可加入房间。

			NoAutoKickUser: bool 类型，可选，禁止自动踢人（抢流）。默认为 false ，即同一个身份的 client (app/room/user) ，新的连麦请求可以成功，旧连接被关闭。

		:return:
			200 OK
			{
			    "appId": "<AppID>",
			    "hub": "<Hub>",
			    "title": "<Title>",
			    "maxUsers": <MaxUsers>,
			    "noAutoCloseRoom": <NoAutoCloseRoom>,
			    "noAutoCreateRoom": <NoAutoCreateRoom>,
			    "noAutoKickUser": <NoAutoKickUser>,
			    "createdAt": <CreatedAt>,
			    "updatedAt": <UpdatedAt>
			}
			616
			{
			    "error": "hub not match"
			}
		"""


		return self.__post(self.host+'/v3/apps',data,)


	def GetApp(self, appid=None):
		"""
		Host rtc.qiniuapi.com
		GET /v3/apps/<AppID>
		Authorization: qiniu mac

		:param appid:
			AppID: app 的唯一标识。 可以不填写，不填写的话，默认就是输出所有app的相关信息

		:return:
			200 OK
			{
			    "appId": "<AppID>",
			    "hub": "<Hub>",
			    "title": "<Title>",
			    "maxUsers": <MaxUsers>,
			    "noAutoCloseRoom": <NoAutoCloseRoom>,
			    "noAutoCreateRoom": <NoAutoCreateRoom>,
			    "noAutoKickUser": <NoAutoKickUser>,
			    "mergePublishRtmp": {
			        "audioOnly": <AudioOnly>,
			        "height": <OutputHeight>,
			        "width": <OutputHeight>,
			        "fps": <OutputFps>,
			        "kbps": <OutputKbps>,
			        "url": "<URL>",
			        "streamTitle": "<StreamTitle>"
			    },
			    "createdAt": <CreatedAt>,
			    "updatedAt": <UpdatedAt>
			}

			612
			{
			    "error": "app not found"
			}

		####
			AppID: app 的唯一标识。

			UID: 客户的七牛帐号。

			Hub: 绑定的直播 hub，使用此 hub 的资源进行推流等业务功能，hub 与 app 必须属于同一个七牛账户。

			Title: app 的名称，注意，Title不是唯一标识。

			MaxUsers: int 类型，连麦房间支持的最大在线人数。

			NoAutoCloseRoom: bool 类型，禁止自动关闭房间。

			NoAutoCreateRoom: bool 类型，禁止自动创建房间。

			NoAutoKickUser: bool 类型，禁止自动踢人。

			MergePublishRtmp: 连麦合流转推 RTMP 的配置。

			CreatedAt: time 类型，app 创建的时间。

			UpdatedAt: time 类型，app 更新的时间。
		"""
		if appid:
			return self.__get(self.host+'/v3/apps/%s' % appid )
		else:
			return self.__get(self.host+'/v3/apps' )

	def DeleteApp(self, appid):
		"""
		Host rtc.qiniuapi.com
		DELETE /v3/apps/<AppID>
		Authorization: qiniu mac

		:return:
			200 OK

			612
			{
			    "error": "app not found"
			}
		"""
		return self.__delete(self.host+'/v3/apps/%s' % appid)

	def UpdateApp(self, appid, data):
		"""
		Host rtc.qiniuapi.com
		Post /v3/apps/<AppID>
		Authorization: qiniu mac

		:param appid:
			AppID: app 的唯一标识，创建的时候由系统生成。

			Title: app 的名称， 可选。

			Hub: 绑定的直播 hub，可选，用于合流后 rtmp 推流。

			MaxUsers: int 类型，可选，连麦房间支持的最大在线人数。

			NoAutoCloseRoom: bool 指针类型，可选，true 表示禁止自动关闭房间。

			NoAutoCreateRoom: bool 指针指型，可选，true 表示禁止自动创建房间。

			NoAutoKickUser: bool 类型，可选，禁止自动踢人。

			MergePublishRtmp: 连麦合流转推 RTMP 的配置，可选择。其详细配置包括如下

			Enable: 布尔类型，用于开启和关闭所有房间的合流功能。
			AudioOnly: 布尔类型，可选，指定是否只合成音频。
			Height, Width: int64，可选，指定合流输出的高和宽，默认为 640 x 480。
			OutputFps: int64，可选，指定合流输出的帧率，默认为 25 fps 。
			OutputKbps: int64，可选，指定合流输出的码率，默认为 1000 。
			URL: 合流后转推旁路直播的地址，可选，支持魔法变量配置按照连麦房间号生成不同的推流地址。如果是转推到七牛直播云，不建议使用该配置。
			StreamTitle: 转推七牛直播云的流名，可选，支持魔法变量配置按照连麦房间号生成不同的流名。例如，配置 Hub 为 qn-zhibo ，配置 StreamTitle 为 $(roomName) ，则房间 meeting-001 的合流将会被转推到 rtmp://pili-publish.qn-zhibo.***.com/qn-zhibo/meeting-001地址。详细配置细则，请咨询七牛技术支持。

		:return:
			200 OK
			{
			    "appId": "<AppID>",
			    "hub": "<Hub>",
			    "title": "<Title>",
			    "maxUsers": <MaxUsers>,
			    "noAutoCloseRoom": <NoAutoCloseRoom>,
			    "noAutoCreateRoom": <NoAutoCreateRoom>,
			    "noAutoKickUser": <NoAutoKickUser>,
			    "mergePublishRtmp": {
			        "enable": <Enable>,
			        "audioOnly": <AudioOnly>,
			        "height": <OutputHeight>,
			        "width": <OutputHeight>,
			        "fps": <OutputFps>,
			        "kbps": <OutputKbps>,
			        "url": "<URL>",
			        "streamTitle": "<StreamTitle>"
			    },
			    "createdAt": <CreatedAt>,
			    "updatedAt": <UpdatedAt>
			}

			612
			{
			    "error": "app not found"
			}
			616
			{
			    "error": "hub not match"
			}
		"""

		return self.__post(self.host+'/v3/apps/%s' % appid , data,)

	def ListUser(self, AppID, RoomName):
		"""
		Host rtc.qiniuapi.com
		GET /v3/apps/<AppID>/rooms/<RoomName>/users
		Authorization: qiniu mac

		:param:
			AppID: 连麦房间所属的 app 。

			RoomName: 操作所查询的连麦房间。

		:return:
			200 OK
			{
			    "users": [
			        {
			            "userId": "<UserID>"
			        },
			    ]
			}
			612
			{
			    "error": "app not found"
			}
		"""
		return self.__get( self.host+'/v3/apps/%s/rooms/%s/users' % (AppID, RoomName))

	def KickUser(self, AppID, RoomName, UserID):
		"""
		Host rtc.qiniuapi.com
		DELETE /v3/apps/<AppID>/rooms/<RoomName>/users/<UserID>
		Authorization: qiniu mac

		:param:
			AppID: 连麦房间所属的 app 。

			RoomName: 连麦房间。

			UserID: 操作所剔除的用户。

		:return:
			200 OK
			612
			{
			    "error": "app not found"
			}
			612
			{
			    "error": "user not found"
			}
			615
			{
			    "error": "room not active"
			}
		"""
		return self.__delete( self.host+'/v3/apps/%s/rooms/%s/users/%s' % (AppID, RoomName, UserID) )

	def ListActiveRoom(self, AppID, RoomNamePrefix=None):
		"""
		Host rtc.qiniuapi.com
		GET /v3/apps/<AppID>/rooms?prefix=<RoomNamePrefix>&offset=<Offset>&limit=<Limit>
		Authorization: qiniu mac

		:param:
			AppID: 连麦房间所属的 app 。

			RoomNamePrefix: 所查询房间名的前缀索引，可以为空。

			Offset: int 类型，分页查询的位移标记。

			Limit: int 类型，此次查询的最大长度。

		:return:
			200 OK
			{
			    "end": <IsEnd>,
			    "offset": <Offset>,
			    "rooms": [
			            "<RoomName>",
			            ...
			    ]
			}
			612
			{
			    "error": "app not found"
			}
		###
			IsEnd: bool 类型，分页查询是否已经查完所有房间。

			Offset: int 类型，下次分页查询使用的位移标记。

			RoomName: 当前活跃的房间名。
		"""
		if RoomNamePrefix:
			return self.__get( self.host+'/v3/apps/%s/rooms?prefix=%s' % (AppID, RoomNamePrefix) )
		else:
			return self.__get( self.host+'/v3/apps/%s/rooms' % AppID )

	def __post(self, url, data=None):
		return http._post_with_qiniu_mac(url, data, self.auth)

	def __get(self, url, params=None):
		return http._get_with_qiniu_mac(url,params,self.auth)

	def __delete(self, url, params=None):
		return http._delete_with_qiniu_mac(url,params,self.auth)


def RtcRoomToken(access_key, secret_key, roomAccess ):
	"""
	:arg:
		AppID: 房间所属帐号的 app 。

		RoomName: 房间名称，需满足规格 ^[a-zA-Z0-9_-]{3,64}$

		UserID: 请求加入房间的用户 ID，需满足规格 ^[a-zA-Z0-9_-]{3,50}$

		ExpireAt: int64 类型，鉴权的有效时间，传入以秒为单位的64位Unix绝对时间，token 将在该时间后失效。

		Permission: 该用户的房间管理权限，"admin" 或 "user"，默认为 "user" 。当权限角色为 "admin" 时，拥有将其他用户移除出房间等特权.

	:method:
		# 1. 定义房间管理凭证，并对凭证字符做URL安全的Base64编码
		roomAccess = {
		    "appId": "<AppID>"
		    "roomName": "<RoomName>",
		    "userId": "<UserID>",
		    "expireAt": <ExpireAt>,
		    "permission": "<Permission>"
		}
		roomAccessString = json_to_string(roomAccess)
		encodedRoomAccess = urlsafe_base64_encode(roomAccessString)

		# 2. 计算HMAC-SHA1签名，并对签名结果做URL安全的Base64编码
		sign = hmac_sha1(encodedRoomAccess, <SecretKey>)
		encodedSign = urlsafe_base64_encode(sign)

		# 3. 将AccessKey与以上两者拼接得到房间鉴权
		roomToken = "<AccessKey>" + ":" + encodedSign + ":" + encodedRoomAccess
	"""
	def b(data):
		return bytes(data)

	def urlsafe_base64_encode(data):
		ret = base64.urlsafe_b64encode(b(data))
		return b(ret)

	def pre_token(data, SecretKey):
		data = b(data)
		SecretKey = b(SecretKey)
		hashed = hmac.new(SecretKey, data, hashlib.sha1)
		return urlsafe_base64_encode(hashed.digest())


	roomAccessString = json.dumps(roomAccess)
	byte_result = bytes(roomAccessString, 'utf-8' )
	encodedRoomAccess = base64.urlsafe_b64encode( byte_result   )

	encodedSign = pre_token( encodedRoomAccess, secret_key )

	#roomToken = bytes(access_key, 'utf-8') + bytes(':','utf-8') + encodedSign + bytes(':','utf-8') + encodedRoomAccess
	roomToken = access_key + ':' + str(encodedSign, encoding = "utf-8") + ':' + str(encodedRoomAccess, encoding = "utf-8")

	print ( access_key  )
	print ( encodedSign )
	print ( encodedRoomAccess )
	return roomToken





	#
	# roomAccessString = json.dumps(roomAccess)
	# byte_result = bytes(roomAccessString, 'utf-8' )
	# encodedRoomAccess = base64.urlsafe_b64encode( byte_result   )
	#
	#
	# sign = hmac.new( bytes(secret_key, 'utf-8') , encodedRoomAccess, hashlib.sha1).digest()
	# encodedSign = base64.urlsafe_b64encode( sign   )
	# #roomToken = bytes(access_key, 'utf-8') + bytes(':','utf-8') + encodedSign + bytes(':','utf-8') + encodedRoomAccess
	# roomToken = access_key + ':' + str(encodedSign, encoding = "utf-8") + ':' + str(encodedRoomAccess, encoding = "utf-8")
	#
	# print ( access_key  )
	# print ( encodedSign )
	# print ( encodedRoomAccess )
	# return roomToken








	# roomAccessString = json.dumps(roomAccess)
	# byte_result = bytes(roomAccessString, 'utf-8' )
	# encodedRoomAccess = base64.urlsafe_b64encode( byte_result   )
	# print ( type(encodedRoomAccess ) )
	# #print (encodedRoomAccess)
	#
	# sign = hmac.new( bytes( secret_key, 'utf-8' ) , encodedRoomAccess, hashlib.sha1).digest()
	# encodedSign = base64.urlsafe_b64encode( sign   )
	# #roomToken = bytes(access_key, 'utf-8') + bytes(':','utf-8') + encodedSign + bytes(':','utf-8') + encodedRoomAccess
	# roomToken = access_key + ':' + str(encodedSign, encoding = "utf-8") + ':' + str(encodedRoomAccess, encoding = "utf-8")
	#
	# print ( access_key  )
	# print ( encodedSign )
	# print ( encodedRoomAccess )
	# return roomToken










