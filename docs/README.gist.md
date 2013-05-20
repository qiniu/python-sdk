Qiniu Resource (Cloud) Storage SDK for Python
===

# Python 2.x SDK 使用指南

此 Python SDK 适用于2.x版本，基于 [七牛云存储官方API](http://docs.qiniutek.com/v3/api/) 构建。使用此 SDK 构建您的网络应用程序，能让您以非常便捷地方式将数据安全地存储到七牛云存储上。无论您的网络应用是一个网站程序，还是包括从云端（服务端程序）到终端（手持设备应用）的架构的服务或应用，通过七牛云存储及其 SDK，都能让您应用程序的终端用户高速上传和下载，同时也让您的服务端更加轻盈。

目录
----
- [1. 安装](#install)
- [2. 初始化](#setup)
	- [2.1 配置密钥](#setup-key)
- [3. 资源管理接口](#rs-api)
	- [3.1 查看单个文件属性信息](#rs-stat)
	- [3.2 复制单个文件](#rs-copy)
	- [3.3 移动单个文件](#rs-move)
	- [3.4 删除单个文件](#rs-delete)
	- [3.5 批量操作](#batch)
		- [3.5.1 批量获取文件属性信息](#batch-stat)
		- [3.5.2 批量复制文件](#batch-copy)
		- [3.5.3 批量移动文件](#batch-move)
		- [3.5.4 批量删除文件](#batch-delete)
- [4. 上传下载接口](#get-and-put-api)
	- [4.1 上传下载授权](#token)
		- [4.1.1 生成uptoken](#make-uptoken)
		- [4.1.2 生成downtoken](#make-downtoken)
	- [4.2 文件上传](#upload)
		- [4.2.1 普通上传](#io-upload)
		- [4.2.2 断点续上传](#resumable-io-upload)
	- [4.3 文件下载](#io-download)
		- [4.3.1 公有资源下载](#public-download)
		- [4.3.2 私有资源下载](#private-download)
- [5. 数据处理接口](#fop-api)
	- [5.1 图像](#fop-image)
		- [5.1.1 查看图像属性](#fop-image-info)
		- [5.1.2 查看图片EXIF信息](#fop-exif)
		- [5.1.3 生成图片预览](#fop-image-view)
- [6. 贡献代码](#contribution)
- [7. 许可证](#license)

----

<a name=install></a>
## 1. 安装
在命令行下执行

	git clone http://github.com/qiniu/python-sdk
	# 将系统路径添加到python 的搜索路径

<a name=setup-key></a>
### 2.1 配置密钥

要接入七牛云存储，您需要拥有一对有效的 Access Key 和 Secret Key 用来进行签名认证。可以通过如下步骤获得：

1. [开通七牛开发者帐号](https://dev.qiniutek.com/signup)
2. [登录七牛开发者自助平台，查看 Access Key 和 Secret Key](https://dev.qiniutek.com/account/keys) 。

在获取到 Access Key 和 Secret Key 之后，您可以在您的程序中调用如下两行代码进行初始化对接, 要确保`ACCESS_KEY` 和 `SECRET_KEY` 在调用所有七牛API服务之前均已赋值：

```{python}
@gist(gist/conf.py#config)
```

<a name=rs-api></a>
## 3. 资源管理接口

<a name=rs-stat></a>
### 3.1 查看单个文件属性信息
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#stat)
```

<a name=rs-copy></a>
### 3.2 复制单个文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#copy)
```

<a name=rs-move></a>
### 3.3 移动单个文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#move)
```

<a name=rs-delete></a>
### 3.4 删除单个文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#move)
```

<a name=batch></a>
### 3.5 批量操作
当您需要一次性进行多个操作时, 可以使用批量操作.
<a name=batch-stat></a>
#### 3.5.1 批量获取文件属性信息
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#batch_path)

@gist(../demo.py#batch_stat)
```

<a name=batch-copy></a>
#### 3.5.2 批量复制文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#batch_path)

@gist(../demo.py#batch_copy)
```

<a name=batch-move></a>
#### 3.5.3 批量移动文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#batch_path)

@gist(../demo.py#batch_move)
```

<a name=batch-delete></a>
#### 3.5.4 批量删除文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_rs)

@gist(../demo.py#batch_path)

@gist(../demo.py#batch_delete)
```

<a name=get-and-put-api></a>
## 4. 上传下载接口

<a name=token></a>
### 4.1 上传下载授权
<a name=make-uptoken></a>
#### 4.1.1 上传授权uptoken
uptoken是一个字符串，作为http协议Header的一部分（Authorization字段）发送到我们七牛的服务端，表示这个http请求是经过认证的。
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_token)

@gist(../demo.py#uptoken)
```

#### 4.1.2 下载授权downtoken
downtoken的原理同上，用来生成downtoken的GetPolicy

```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_token)

@gist(../demo.py#dntoken)
```

<a name=upload></a>
### 4.2 文件上传
**注意**：如果您只是想要上传已存在您电脑本地或者是服务器上的文件到七牛云存储，可以直接使用七牛提供的 [qrsync](/v3/tools/qrsync/) 上传工具。
文件上传有两种方式，一种是以普通方式直传文件，简称普通上传，另一种方式是断点续上传，断点续上传在网络条件很一般的情况下也能有出色的上传速度，而且对大文件的传输非常友好。

<a name=io-upload></a>
### 4.2.1 普通上传
普通上传的接口在 `qiniu.io` 里，如下：

直接上传二进制流
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_io)

@gist(../demo.py#put)
```

上传本地文件

```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_io)

@gist(../demo.py#put_file)
```

<a name=resumable-io-upload></a>
### 4.2.2 断点续上传
上传二进制流
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_resumable_io)

@gist(../demo.py#resumable_put)
```

上传本地文件
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_resumable_io)

@gist(../demo.py#resumable_put_file)
```

<a name=io-download></a>
### 4.3 文件下载
七牛云存储上的资源下载分为 公有资源下载 和 私有资源下载 。

私有（private）是 Bucket（空间）的一个属性，一个私有 Bucket 中的资源为私有资源，私有资源不可匿名下载。

新创建的空间（Bucket）缺省为私有，也可以将某个 Bucket 设为公有，公有 Bucket 中的资源为公有资源，公有资源可以匿名下载。

<a name=public-download></a>
#### 4.3.1 公有资源下载
如果在给bucket绑定了域名的话，可以通过以下地址访问。

	[GET] http://<domain>/<key>

其中<domain>可以到[七牛云存储开发者自助网站](https://dev.qiniutek.com/buckets)绑定, 域名可以使用自己一级域名的或者是由七牛提供的二级域名(`<bucket>.qiniutek.com`)。注意，尖括号不是必需，代表替换项。

<a name=private-download></a>
#### 4.3.2 私有资源下载
私有资源必须通过临时下载授权凭证(downloadToken)下载，如下：

	[GET] http://<domain>/<key>?token=<downloadToken>

注意，尖括号不是必需，代表替换项。  
`downloadToken` 可以使用 SDK 提供的如下方法生成：

<a name=fop-api></a>
## 5. 数据处理接口
七牛支持在云端对图像, 视频, 音频等富媒体进行个性化处理

<a name=fop-image></a>
### 5.1 图像
<a name=fop-image-info></a>
### 5.1.1 查看图像属性
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_fop)

@gist(../demo.py#image_info)
```

<a name=fop-exif></a>
### 5.1.2 查看图片EXIF信息
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_fop)

@gist(../demo.py#exif)
```


<a name=fop-image-view></a>
### 5.1.3 生成图片预览
```{python}
@gist(gist/conf.py#config)

@gist(../demo.py#import_fop)

@gist(../demo.py#image_view)
```

<a name=contribution></a>
## 6. 贡献代码

1. Fork
2. 创建您的特性分支 (`git checkout -b my-new-feature`)
3. 提交您的改动 (`git commit -am 'Added some feature'`)
4. 将您的修改记录提交到远程 `git` 仓库 (`git push origin my-new-feature`)
5. 然后到 github 网站的该 `git` 远程仓库的 `my-new-feature` 分支下发起 Pull Request

<a name=license></a>
## 7. 许可证

Copyright (c) 2013 qiniu.com

基于 MIT 协议发布:

* [www.opensource.org/licenses/MIT](http://www.opensource.org/licenses/MIT)

