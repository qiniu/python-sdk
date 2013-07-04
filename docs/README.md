---
title: Python SDK 使用指南 | 七牛云存储
---

# Python SDK 使用指南

此 Python SDK 适用于2.x版本，基于 [七牛云存储官方API](http://docs.qiniu.com/) 构建。使用此 SDK 构建您的网络应用程序，能让您以非常便捷地方式将数据安全地存储到七牛云存储上。无论您的网络应用是一个网站程序，还是包括从云端（服务端程序）到终端（手持设备应用）的架构的服务或应用，通过七牛云存储及其 SDK，都能让您应用程序的终端用户高速上传和下载，同时也让您的服务端更加轻盈。

SDK 下载地址：<https://github.com/qiniu/python-sdk/tags>

**文档大纲**

- [概述](#overview)
- [准备开发环境](#prepare)
	- [安装](#install)
	- [ACCESS_KEY 和 SECRET_KEY](#appkey)
- [使用SDK](#sdk-usage)
	- [初始化环境](#init)
	- [上传文件](#io-put)
		- [上传流程](#io-put-flow)
			- [上传策略](#io-put-policy)
			- [上传凭证](#upload-token)
			- [PutExtra](#put-extra)
			- [上传文件](#upload-do)
			- [断点续上传、分块并行上传](#resumable-io-put)
	- [下载文件](#io-get)
		- [下载公有文件](#io-get-public)
		- [下载私有文件](#io-get-private)
		- [断点续下载](#resumable-io-get)
	- [资源操作](#rs)
		- [获取文件信息](#rs-stat)
		- [复制文件](#rs-copy)
		- [移动文件](#rs-move)
		- [删除文件](#rs-delete)
		- [批量操作](#rs-batch)
			- [批量获取文件信息](#batch-stat)
			- [批量复制文件](#batch-copy)
			- [批量移动文件](#batch-move)
			- [批量删除文件](#batch-delete)
	- [高级管理操作](#rsf)
		- [列出文件](#list-prefix)
	- [云处理](#fop)
		- [图像](#fop-image)
			- [查看图像属性](#fop-image-info)
			- [查看图片EXIF信息](#fop-exif)
			- [生成图片预览](#fop-image-view)
- [贡献代码](#contribution)
- [许可证](#license)

<a name="overview"></a>

## 概述

七牛云存储的 Python 语言版本 SDK（本文以下称 Python-SDK）是对七牛云存储API协议的一层封装，以提供一套对于 Python 开发者而言简单易用的开发工具。Python 开发者在对接 Python-SDK 时无需理解七牛云存储 API 协议的细节，原则上也不需要对 HTTP 协议和原理做非常深入的了解，但如果拥有基础的 HTTP 知识，对于出错场景的处理可以更加高效。

Python-SDK 被设计为同时适合服务器端和客户端使用。服务端是指开发者自己的业务服务器，客户端是指开发者提供给终端用户的软件，通常运行在 Windows/Mac/Linux 这样的桌面平台上。服务端因为有七牛颁发的 AccessKey/SecretKey，可以做很多客户端做不了的事情，比如删除文件、移动/复制文件等操作。一般而言，客服端操作文件需要获得服务端的授权。客户端上传文件需要获得服务端颁发的 [uptoken（上传授权凭证）](http://docs.qiniu.com/api/put.html#uploadToken)，客户端下载文件（包括下载处理过的文件，比如下载图片的缩略图）需要获得服务端颁发的 [dntoken（下载授权凭证）](http://docs.qiniu.com/api/get.html#download-token)。但开发者也可以将 bucket 设置为公开，此时文件有永久有效的访问地址，不需要业务服务器的授权，这对网站的静态文件（如图片、js、css、html）托管非常方便。

从 v5.0.0 版本开始，我们对 SDK 的内容进行了精简。所有管理操作，比如：创建/删除 bucket、为 bucket 绑定域名（publish）、设置数据处理的样式分隔符（fop seperator）、新增数据处理样式（fop style）等都去除了，统一建议到[开发者后台](https://portal.qiniu.com/)来完成。另外，此前服务端还有自己独有的上传 API，现在也推荐统一成基于客户端上传的工作方式。

从内容上来说，Python-SDK 主要包含如下几方面的内容：

* 公共部分，所有用况下都用到：qiniu/rpc.py, qiniu/httplib_chunk.py
* 客户端上传文件：qiniu/io.py
* 客户端断点续上传：qiniu/resumable_io.py
* 数据处理：qiniu/fop.py
* 服务端操作：qiniu/auth/digest.py, qiniu/auth/up.py (授权), qiniu/rs/rs.py, qiniu/rs/rs_token.py (资源操作, uptoken/dntoken颁发)



<a name="prepare"></a>

## 准备开发环境


<a name="install"></a>

### 安装

直接安装:
	
	pip install qiniu
	#或
	easy_install qiniu

Tornado is listed in PyPI and can be installed with pip or easy_install. Note that the source distribution includes demo applications that are not present when Tornado is installed in this way, so you may wish to download a copy of the source tarball as well.
Python-SDK可以使用`pip`或`easy_install`从PyPI服务器上安装，但不包括文档和样例。如果需要，请下载源码并安装。

源码安装：

从[Python-SDK下载地址](https://github.com/qiniu/python-sdk/releases)下载源码：

	tar xvzf python-sdk-$VERSION.tar.gz
	cd python-sdk-$VERSION
	python setup.py install


<a name="appkey"></a>

### ACCESS_KEY 和 SECRET_KEY

在使用SDK 前，您需要拥有一对有效的 AccessKey 和 SecretKey 用来进行签名授权。

可以通过如下步骤获得：

1. [开通七牛开发者帐号](https://portal.qiniu.com/signup)
2. [登录七牛开发者自助平台，查看 Access Key 和 Secret Key](https://portal.qiniu.com/setting/key) 。

<a name="sdk-usage"></a>

## 使用SDK

<a name="init"></a>

### 初始化环境

在获取到 Access Key 和 Secret Key 之后，您可以在您的程序中调用如下两行代码进行初始化对接, 要确保`ACCESS_KEY` 和 `SECRET_KEY` 在调用所有七牛API服务之前均已赋值：

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"
```

<a name="io-put"></a>

### 上传文件

为了尽可能地改善终端用户的上传体验，七牛云存储首创了客户端直传功能。一般云存储的上传流程是：

    客户端（终端用户） => 业务服务器 => 云存储服务

这样多了一次上传的流程，和本地存储相比，会相对慢一些。但七牛引入了客户端直传，将整个上传过程调整为：

    客户端（终端用户） => 七牛 => 业务服务器

客户端（终端用户）直接上传到七牛的服务器，通过DNS智能解析，七牛会选择到离终端用户最近的ISP服务商节点，速度会比本地存储快很多。文件上传成功以后，七牛的服务器使用回调功能，只需要将非常少的数据（比如Key）传给应用服务器，应用服务器进行保存即可。

<a name="io-put-flow"></a>

#### 上传流程

在七牛云存储中，整个上传流程大体分为这样几步：

1. 业务服务器颁发 [uptoken（上传授权凭证）](http://docs.qiniu.com/api/put.html#uploadToken)给客户端（终端用户）
2. 客户端凭借 [uptoken](http://docs.qiniu.com/api/put.html#uploadToken) 上传文件到七牛
3. 在七牛获得完整数据后，发起一个 HTTP 请求回调到业务服务器
4. 业务服务器保存相关信息，并返回一些信息给七牛
5. 七牛原封不动地将这些信息转发给客户端（终端用户）

需要注意的是，回调到业务服务器的过程是可选的，它取决于业务服务器颁发的 [uptoken](http://docs.qiniu.com/api/put.html#uploadToken)。如果没有回调，七牛会返回一些标准的信息（比如文件的 hash）给客户端。如果上传发生在业务服务器，以上流程可以自然简化为：

1. 业务服务器生成 uptoken（不设置回调，自己回调到自己这里没有意义）
2. 凭借 [uptoken](http://docs.qiniu.com/api/put.html#uploadToken) 上传文件到七牛
3. 善后工作，比如保存相关的一些信息

<a name="io-put-policy"></a>

##### 上传策略

[uptoken](http://docs.qiniu.com/api/put.html#uploadToken) 实际上是用 AccessKey/SecretKey 进行数字签名的上传策略(`qiniu/rs/PutPolicy`)，它控制则整个上传流程的行为。让我们快速过一遍你都能够决策啥：

```{python}
class PutPolicy(object):
	scope = None             # 可以是 bucketName 或者 bucketName:key
	expires = 3600           # 默认是 3600 秒
	callbackUrl = None
	callbackBody = None
	returnUrl = None
	returnBody = None
	endUser = None
	asyncOps = None
```

* `scope` 限定客户端的权限。如果 `scope` 是 bucket，则客户端只能新增文件到指定的 bucket，不能修改文件。如果 `scope` 为 bucket:key，则客户端可以修改指定的文件。
* `callbackUrl` 设定业务服务器的回调地址，这样业务服务器才能感知到上传行为的发生。
* `callbackBody` 设定业务服务器的回调信息。文件上传成功后，七牛向业务服务器的callbackUrl发送的POST请求携带的数据。支持 [魔法变量](http://docs.qiniu.com/api/put.html#MagicVariables) 和 [自定义变量](http://docs.qiniu.com/api/put.html#xVariables)。
* `returnUrl` 设置用于浏览器端文件上传成功后，浏览器执行301跳转的URL，一般为 HTML Form 上传时使用。文件上传成功后浏览器会自动跳转到 `returnUrl?upload_ret=returnBody`。
* `returnBody` 可调整返回给客户端的数据包，支持 [魔法变量](http://docs.qiniu.com/api/put.html#MagicVariables) 和 [自定义变量](http://docs.qiniu.com/api/put.html#xVariables)。`returnBody` 只在没有 `callbackUrl` 时有效（否则直接返回 `callbackUrl` 返回的结果）。不同情形下默认返回的 `returnBody` 并不相同。在一般情况下返回的是文件内容的 `hash`，也就是下载该文件时的 `etag`；但指定 `returnUrl` 时默认的 `returnBody` 会带上更多的信息。
* `asyncOps` 可指定上传完成后，需要自动执行哪些数据处理。这是因为有些数据处理操作（比如音视频转码）比较慢，如果不进行预转可能第一次访问的时候效果不理想，预转可以很大程度改善这一点。

关于上传策略更完整的说明，请参考 [uptoken](http://docs.qiniu.com/api/put.html#uploadToken)。

<a name="upload-token"></a>

##### 上传凭证

服务端生成 [uptoken](http://docs.qiniu.com/api/put.html#uploadToken) 代码如下：

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

policy = qiniu.rs.PutPolicy(bucket_name)
uptoken = policy.token()
```

<a name="put-extra"></a>

##### PutExtra

PutExtra是上传时的可选信息，默认为None

```{python}
class PutExtra(object):
	params = {}
	mime_type = 'application/octet-stream'
	crc32 = ""
	check_crc = 0
```

* `params` 是一个字典。[自定义变量](http://docs.qiniu.com/api/put.html#xVariables)，key必须以 x: 开头命名，不限个数。可以在 uploadToken 的 callbackBody 选项中求值。
* `mime_type` 表示数据的MimeType。
* `crc32` 待检查的crc32值
* `check_crc` 可选值为0, 1, 2。 `check_crc=0`: 表示不进行 crc32 校验。`check_crc=1`: 对于 put 等同于 `check_crc=2`；对于 put_file 会自动计算 crc32 值。`check_crc == 2`: 表示进行 crc32 校验，且 crc32 值就是上面的 crc32 变量

<a name="upload-do"></a>

##### 上传文件

上传文件到七牛（通常是客户端完成，但也可以发生在服务端）：

直接上传二进制流
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.io

extra = qiniu.io.PutExtra()
extra.mime_type = "text/plain"

# data 可以是str或read()able对象
data = StringIO.StringIO("hello!")
ret, err = qiniu.io.put(uptoken, key, data, extra)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```

上传本地文件

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.io

localfile = "%s" % __file__

ret, err = qiniu.io.put_file(uptoken, key, localfile)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```

ret是一个字典，含有`hash`，`key`等信息。

<a name="resumable-io-put"></a>

##### 断点续上传、分块并行上传

除了基本的上传外，七牛还支持你将文件切成若干块（除最后一块外，每个块固定为4M大小），每个块可独立上传，互不干扰；每个分块块内则能够做到断点上续传。

我们来看支持了断点上续传、分块并行上传的基本样例：

上传二进制流
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.resumable_io as rio

class ResumableUpload(object):
	position = 0
	def __init__(self, string_data):
		self.data = string_data
	
	def read(self, length):
		data = self.data[self.position: self.position+length]
		self.position += length
		return data

a = "resumable upload string"
extra = rio.PutExtra(bucket_name)
extra.mime_type = "text/plain"
ret, err = rio.put(uptoken, key, ResumableUpload(a), len(a), extra)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
print ret,
```

上传本地文件
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.resumable_io as rio

localfile = "%s" % __file__
extra = rio.PutExtra(bucket_name)

ret, err = rio.put_file(uptoken, key, localfile, extra)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
print ret,
```

<a name="io-get"></a>

### 下载文件

<a name="io-get-public"></a>

#### 下载公有文件

每个 bucket 都会绑定一个或多个域名（domain）。如果这个 bucket 是公开的，那么该 bucket 中的所有文件可以通过一个公开的下载 url 可以访问到：

    http://<domain>/<key>

假设某个 bucket 既绑定了七牛的二级域名，如 hello.qiniudn.com，也绑定了自定义域名（需要备案），如 hello.com。那么该 bucket 中 key 为 a/b/c.htm 的文件可以通过 http://hello.qiniudn.com/a/b/c.htm 或 http://hello.com/a/b/c.htm 中任意一个 url 进行访问。

<a name="io-get-private"></a>

#### 下载私有文件

如果某个 bucket 是私有的，那么这个 bucket 中的所有文件只能通过一个的临时有效的 downloadUrl 访问：

    http://<domain>/<key>?e=<deadline>&token=<dntoken>

其中 dntoken 是由业务服务器签发的一个[临时下载授权凭证](http://docs.qiniu.com/api/get.html#download-token)，deadline 是 dntoken 的有效期。dntoken不需要单独生成，SDK 提供了生成完整 downloadUrl 的方法（包含了 dntoken），示例代码如下：

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

base_url = qiniu.rs.make_base_url(domain, key)
policy = qiniu.rs.GetPolicy()
private_url = policy.make_request(base_url)
```

生成 downloadUrl 后，服务端下发 downloadUrl 给客户端。客户端收到 downloadUrl 后，和公有资源类似，直接用任意的 HTTP 客户端就可以下载该资源了。唯一需要注意的是，在 downloadUrl 失效却还没有完成下载时，需要重新向服务器申请授权。

无论公有资源还是私有资源，下载过程中客户端并不需要七牛 SDK 参与其中。

<a name="resumable-io-get"></a>

#### 断点续下载

无论是公有资源还是私有资源，获得的下载 url 支持标准的 HTTP 断点续传协议。考虑到多数语言都有相应的断点续下载支持的成熟方法，七牛 C-SDK 并不提供断点续下载相关代码。

<a name="rs"></a>

### 资源操作

<!--TODO:资源操作介绍-->

<a name="rs-stat"></a>
#### 获取文件信息

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

ret, err = qiniu.rs.Client().stat(bucket_name, key)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
print ret,
```


<a name="rs-copy"></a>
#### 复制文件

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

ret, err = qiniu.rs.Client().copy(bucket_name, key, bucket_name, key2)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```


<a name="rs-move"></a>
#### 移动文件

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

ret, err = qiniu.rs.Client().move(bucket_name, key2, bucket_name, key3)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```


<a name="rs-delete"></a>
#### 删除文件

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

ret, err = qiniu.rs.Client().delete(bucket_name, key3)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```


<a name="rs-batch"></a>
#### 批量操作

当您需要一次性进行多个操作时, 可以使用批量操作。


<a name="batch-stat"></a>
##### 批量获取文件信息
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

path_1 = qiniu.rs.EntryPath(bucket_name, key)
path_2 = qiniu.rs.EntryPath(bucket_name, key2)
path_3 = qiniu.rs.EntryPath(bucket_name, key3)

rets, err = qiniu.rs.Client().batch_stat([path_1, path_2, path_3])
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
```

<a name="batch-copy"></a>
##### 批量复制文件
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

path_1 = qiniu.rs.EntryPath(bucket_name, key)
path_2 = qiniu.rs.EntryPath(bucket_name, key2)
path_3 = qiniu.rs.EntryPath(bucket_name, key3)

pair_1 = qiniu.rs.EntryPathPair(path_1, path_3)
rets, err = qiniu.rs.Client().batch_copy([pair_1])
if not rets[0]['code'] == 200:
	sys.stderr.write('error: %s ' % "复制失败")
	return
```

<a name="batch-move"></a>
##### 批量移动文件
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

path_1 = qiniu.rs.EntryPath(bucket_name, key)
path_2 = qiniu.rs.EntryPath(bucket_name, key2)
path_3 = qiniu.rs.EntryPath(bucket_name, key3)

pair_2 = qiniu.rs.EntryPathPair(path_3, path_2)
rets, err = qiniu.rs.Client().batch_move([pair_2])
if not rets[0]['code'] == 200:
	sys.stderr.write('error: %s ' % "移动失败")
	return
```

<a name="batch-delete"></a>
##### 批量删除文件
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rs

path_1 = qiniu.rs.EntryPath(bucket_name, key)
path_2 = qiniu.rs.EntryPath(bucket_name, key2)
path_3 = qiniu.rs.EntryPath(bucket_name, key3)

rets, err = qiniu.rs.Client().batch_delete([path_1, path_2])
if not [ret['code'] for ret in rets] == [200, 200]:
	sys.stderr.write('error: %s ' % "删除失败")
	return
```


<a name="rsf"></a>
### 高级管理操作

<a name="list-prefix"></a>
#### 列出文件

请求某个存储空间（bucket）下的文件列表，如果有前缀，可以按前缀（prefix）进行过滤；如果前一次返回marker就表示还有资源，下一步请求需要将marker参数填上。

```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.rsf

rets, err = qiniu.rsf.Client().list_prefix(bucket_name, prefix="test", limit=2)
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
print rets

# 从上一次list_prefix的位置继续列出文件
rets2, err = qiniu.rsf.Client().list_prefix(bucket_name, prefix="test", limit=1, marker=rets['marker'])
if err is not None:
	sys.stderr.write('error: %s ' % err)
	return
print rets2
```
<a name="fop"></a>
### 云处理

<a name="fop-image"></a>
#### 图像

<a name="fop-image-info"></a>
##### 查看图像属性
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.fop
import qiniu.rs

# 生成base_url
url = qiniu.rs.make_base_url(domain, pic_key)

# 生成fop_url
image_info = qiniu.fop.ImageInfo()
url = image_info.make_request(url)

# 对其签名，生成private_url。如果是公有bucket此步可以省略
policy = qiniu.rs.GetPolicy()
url = policy.make_request(url)

print '可以在浏览器浏览: %s' % url
```

<a name="fop-exif"></a>
##### 查看图片EXIF信息
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.fop
import qiniu.rs

# 生成base_url
url = qiniu.rs.make_base_url(domain, pic_key)

# 生成fop_url
image_exif = qiniu.fop.Exif()
url = image_exif.make_request(url)

# 对其签名，生成private_url。如果是公有bucket此步可以省略
policy = qiniu.rs.GetPolicy()
url = policy.make_request(url)

print '可以在浏览器浏览: %s' % url
```


<a name="fop-image-view"></a>
##### 生成图片预览
```{python}
import qiniu.conf

qiniu.conf.ACCESS_KEY = "<YOUR_APP_ACCESS_KEY>"
qiniu.conf.SECRET_KEY = "<YOUR_APP_SECRET_KEY>"

import qiniu.fop
import qiniu.rs

iv = qiniu.fop.ImageView()
iv.width = 100

# 生成base_url
url = qiniu.rs.make_base_url(domain, pic_key)
# 生成fop_url
url = iv.make_request(url)
# 对其签名，生成private_url。如果是公有bucket此步可以省略
policy = qiniu.rs.GetPolicy()
url = policy.make_request(url)
print '可以在浏览器浏览: %s' % url
```

<a name="contribution"></a>
## 贡献代码

+ Fork
+ 创建您的特性分支 (git checkout -b my-new-feature)
+ 提交您的改动 (git commit -am 'Added some feature')
+ 将您的修改记录提交到远程 git 仓库 (git push origin my-new-feature)
+ 然后到 github 网站的该 git 远程仓库的 my-new-feature 分支下发起 Pull Request

<a name="license"></a>
## 许可证

> Copyright (c) 2013 qiniu.com

基于 MIT 协议发布:

> [www.opensource.org/licenses/MIT](http://www.opensource.org/licenses/MIT)
 

