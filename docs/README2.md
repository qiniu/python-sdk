---
title: Python 2.x SDK | 七牛云存储
---

# Python 2.x SDK 使用指南

此 SDK 适用于 Python 2.x 版本，基于[七牛云存储官方API](http://docs.qiniutek.com/v3/api/) 构建。使用此 SDK 构建您的网络应用程序，能让您以非常便捷地方式将数据安全地存储到七牛云存储上。无论您的网络应用是一个网站程序，还是包括从云端（服务端程序）到终端（手持设备应用）的架构的服务或应用，通过七牛云存储及其 SDK，都能让您应用程序的终端用户高速上传和下载，同时也让您的服务端更加轻盈

七牛云存储 Python SDK 源码地址：<https://github.com/qiniu/python-sdk>

SDK 使用依赖Python第三方HTTP CLient：<http://code.google.com/p/httplib2/>

**目录**

- [安装](#Installation)
- [接入](#turn-on)
    - [配置密钥（AccessKey / SecretKey）](#establish_connection!)
    - [针对 Django 网站应用初始化设置](#python-init)
- [使用](#Usage)
    - [文件上传](#upload)
        - [生成上传授权凭证（uploadToken）](#generate-upload-token)
        - [Ruby 服务端上传文件](#upload-server-side)
            - [开启断点续上传](#resumable-upload)
        - [iOS / Android / Web 端直传文件说明](#upload-client-side)
    - [文件下载](#download)
        - [公有资源下载](#download-public-files)
        - [私有资源下载](#download-private-files)
            - [生成下载授权凭证（downloadToken）](#download-token)
        - [高级特性](#other-download-features)
            - [断点续下载](#resumable-download)
            - [自定义 404 NotFound](#upload-file-for-not-found)
    - [文件管理](#file-management)
        - [查看单个文件属性信息](#stat)
        - [复制单个文件](#copy)
        - [移动单个文件](#move)
        - [删除单个文件](#delete)
        - [批量操作](#batch)
            - [批量获取文件属性信息](#batch-get)
            - [批量复制文件](#batch-copy)
            - [批量移动文件](#batch-move)
            - [批量删除文件](#batch-delete)
    - [云处理](#cloud-processing)
        - [图像](#image-processing)
            - [查看图片属性信息](#image-info)
            - [查看图片EXIF信息](#image-exif)
            - [图像在线处理（缩略、裁剪、旋转、转化）](#image-mogrify-for-preview)
            - [图像在线处理（缩略、裁剪、旋转、转化）后并持久化存储](#image-mogrify-for-save-as)
        - 音频(TODO)
        - 视频(TODO)
- [贡献代码](#Contributing)
- [许可证](#License)

<a name="Installation"></a>

## 安装

<a name="turn-on"></a>

## 接入

<a name="establish_connection!"></a>

### 配置秘钥（AccessKey / SecretKey)

要接入七牛云存储，您需要拥有一对有效的 Access Key 和 Secret Key 用来进行签名认证。可以通过如下步骤获得：

1. [开通七牛开发者帐号](https://dev.qiniutek.com/signup)
2. [登录七牛开发者自助平台，查看 Access Key 和 Secret Key](https://dev.qiniutek.com/account/keys)


首先，到 [https://github.com/qiniu/python-sdk/tags](https://github.com/qiniu/python-sdk/tags) 下载SDK源码。

然后，您可以解压 SDK 包后将其放入您项目工程相应的目录中。在引入 SDK 里边的文件后，您需要修改下配置项：

    import config

    config.ACCESS_KEY = '<Please apply your access key>'
    config.SECRET_KEY = '<Dont send your secret key to anyone>'

在完成 Access Key 和 Secret Key 配置后，您就可以正常使用该 SDK 提供的功能了，这些功能接下来会一一介绍。

<a name="python-init"></a>
### 针对 Python 应用初始化设置

新建存储空间（Bucket）的意义在于，您可以将所有上传的资源分布式加密存储在七牛云存储服务端后还能保持相应的完整映射索引。

可以通过 SDK 提供的 `Mkbucket` 函数创建一个 Bucket 。

    resp = rs.Mkbucket(BucketName)

**参数**

**BucketName**
: 必填，字符串（String）类型，空间名称，不能含有特殊字符。　

初始化空间（Bucket）对象后，后续可以在该空间对象的基础上对该空间进行各种操作。　

    client = digestoauth.Client()
    bucket = 'bucket_name'
    rs = qboxrs.Service(client, bucket)

<a name="Usage"></a>

## 使用

<a name="upload"></a>

### 文件上传

**注意**：如果您只是想要上传已存在您电脑本地或者是服务器上的文件到七牛云存储，可以直接使用七牛提供的 [qrsync](http://docs.qiniutek.com/v3/tools/qrsync/) 上传工具。如果是需要通过您的网站或是移动应用(App)上传文件，则可以接入使用此 SDK，详情参考如下文档说明。

<a name="generate-upload-token"></a>

#### 获取用于上传文件的临时授权凭证

要上传一个文件，首先需要调用 SDK 提供的 generate_token 函数来获取一个经过授权用于临时匿名上传的 uploadtoken——经过数字签名的一组数据信息，该 uploadtoken 作为文件上传流中 multipart/form-data 的一部分进行传输。

生成uptoken如下：

    import uptoken
    tokenObj = uptoken.UploadToken(scope, expires_in, callback_url, callback_bodytype, customer)
    uploadtoken = tokenObj.generate_token()

UploadToken 初始化各参数含义如下：

**scope**
: 必须，字符串类型（String），设定文件要上传到的目标 bucket。

**expires_in**
: 可选，数字类型，用于设置上传 URL 的有效期，单位：秒，缺省为 3600 秒，即 1 小时后该上传链接不再有效（但该上传URL在其生成之后的59分59秒都是可用的）。

**callback_url**
: 可选，字符串类型（String），用于设置文件上传成功后，七牛云存储服务端要回调客户方的业务服务器地址。

**callback_bodytype**
: 可选，字符串类型（String），用于设置文件上传成功后，七牛云存储服务端向客户方的业务服务器发送回调请求的 Content-Type。

**customer**
: 可选，字符串类型（String），客户方终端用户（End User）的ID，该字段可以用来标示一个文件的属主，这在一些特殊场景下（比如给终端用户上传的图片打上名字水印）非常有用。

<a name="upload-server-side"></a>

### Python 服务端上传文件

PutFile() 方法可在客户方的业务服务器上直接往七牛云存储上传文件。该函数规格如下：

    import rscli
    resp = rscli.UploadFile(bucket, key, mimeType, localFile, customMeta, callbackParams, uploadToken)

PutFile() 参数含义如下：

    bucket          # 要上传到的目标 bucket 名称
    key		        # 设置文件唯一标识
    mimeType	    # 资源类型，文件的 MIME TYPE，比如 jpg 图片可以是 'image/jpg'
    localFile	    # 本地文件路径，最好是完整的绝对路径
    customMeta	    # 自定义描述信息
    callbackParams 	# 回调参数，格式: "k1=v1&k2=v2&k3=v3..."
    uploadToken		# 此次上传的授权凭证

<a name="resumable-upload"></a>

#### 开启断点续上传
待更新

<a name="upload-client-side"></a>

#### iOS / Android / Web 端直传文件说明

客户端上传流程和服务端上传类似，差别在于：客户端直传文件所需的 `upload_token` 可以选择在客户方的业务服务器端生成，也可以选择在客户方的客户端程序里边生成。选择前者，可以和客户方的业务揉合得更紧密和安全些，比如防伪造请求。

简单来讲，客户端上传流程也分为两步：

1. 生成 `uploadToken`（[用于上传文件的临时授权凭证](#generate-upload-token)）
2. 将该 `uploadToken` 作为文件上传流 `multipart/form-data` 中的一部分实现上传操作

如果您的网络程序是从云端（服务端程序）到终端（手持设备应用）的架构模型，且终端用户有使用您移动端App上传文件（比如照片或视频）的需求，可以把您服务器得到的此 `upload_token` 返回给手持设备端的App，然后您的移动 App 可以使用 [七牛云存储 Objective-SDK （iOS）](http://docs.qiniutek.com/v3/sdk/objc/) 或 [七牛云存储 Android-SDK](http://docs.qiniutek.com/v3/sdk/android/) 的相关上传函数或参照 [七牛云存储API之文件上传](http://docs.qiniutek.com/v3/api/io/#upload) 直传文件。这样，您的终端用户即可把数据（比如图片或视频）直接上传到七牛云存储服务器上无须经由您的服务端中转，而且在上传之前，七牛云存储做了智能加速，终端用户上传数据始终是离他物理距离最近的存储节点。当终端用户上传成功后，七牛云存储服务端会向您指定的 `callback_url` 发送回调数据。如果 `callback_url` 所在的服务处理完毕后输出 `JSON` 格式的数据，七牛云存储服务端会将该回调请求所得的响应信息原封不动地返回给终端应用程序。

网页上传文件，需要满足如下 HTML Form 规格：

    <form method="post" enctype="multipart/form-data" action="http://up.qbox.me/upload">
      <input type="hidden" name="action" value="/rs-put/{urlsafe_b64encode({bucket}:{key})}" />
      <input type="hidden" name="params" value="bucket={bucket}&key={key}&k1=v1&k2=v2&k3=v3&..." />
      <input type="hidden" name="auth" value="{uploadToken}" />
      <input type="file" name="file" />
      <input type="hidden" name="return_url" value="http://DOMAIN/PATH?QUERY_STRING" />
      <input type="submit" value="Upload File" />
    </form>

如上表单结构，其中 `return_url` 字段非必须。倘若有入 `return_url` 字段，七牛云存储会在文件上传成功后执行301跳转，跳转的 URL 即 `return_url` 指定的文本值。七牛云存储执行 301 跳转不影响回调请求的进行，若生成 `uploadToken` 的过程中有指定 `callback_url` 参数，那么回调同样会执行，回调请求POST发送的参数即上述 HTML Form 结构中 `params` 字段指定的值。

以上 HTML Form 结构只满足单个文件上传，大多数时候我们在网页中会用到批量上传，比如使用 `SWFUpload` 或 `jQuery-Ajax-File-Upload` 批量上传组件。使用这些批量上传组件，只需在文件上传前的虚拟Form中动态插入如上 HTML Form 结构中相应的字段即可，`return_url` 除外。关于网页批直传文件的更多细节，您可以向我们的技术支持工程师获得更详细的帮助。

<a name="download"></a>

### 文件下载

要下载一个文件，首先需要取得下载授权，所谓下载授权，就是取得一个临时合法有效的下载链接，只需调用资源表对象的 Get() 方法并传入相应的 文件ID 和下载要保存的文件名 作为参数即可。示例代码如下：

    resp = rs.Get(key, saveAsFriendlyName)


注意，这并不会直接将文件下载并命名为一个 example.jpg 的文件。当请求执行成功，Get() 方法返回的 getRet 变量将会包含如下字段：

    url: <DownloadURL> # 获取文件内容的实际下载地址
    hash: <FileETag>
    fsize: <FileSize>
    mimeType: <MimeType>
    expires:<Seconds> ＃下载url的实际生命周期，精确到秒


这里所说的断点续传指断点续下载，所谓断点续下载，就是已经下载的部分不用下载，只下载基于某个“游标”之后的那部分文件内容。相对于资源表对象的 Get() 方法，调用断点续下载方法 GetIfNotModified() 需额外再传入一个 $baseVersion 的参数作为下载的内容起点。示例代码如下：

    resp = rs.GetIfNotModified(key, saveAsFriendlyName, resp['hash'])

GetIfNotModified() 方法返回的结果包含的字段同 Get() 方法一致。

<a name="download-public-files"></a>

#### 公有资源下载

使用七牛云存储提供的资源发布功能，您可以将一个资源表里边的所有文件以静态链接可访问的方式公开发布到您自己的域名下。
要公开发布一个资源表里边的所有文件，只需调用改资源表对象的 Publish() 方法并传入 域名 作为参数即可。如下示例：

    resp = rs.Publish(YOUR_DOMAIN)

注意：需要到您的域名管理中心将 `YOUR_DOMAIN` CNAME 到 iovip.qbox.me

如果还没有您自己的域名，可将 YOUR_DOMAIN 改成 `<bucketName>.dn.qbox.me` 供临时测试使用。

可以通过 SDK 提供的 `Buckets` 列出所有 bucket（资源表）。

    resp = rs.Buckets()

<a name="rs-Drop"></a>

<a name="download-private-files"></a>

#### 私有资源下载

<a name="download-token"></a>

##### 生成下载授权凭证（downloadToken）

调用资源表对象的 Unpublish() 方法可取消该资源表内所有文件的静态外链。

    resp = rs.Unpublish(YOUR_DOMAIN)

<a name="other-download-features"></a>

#### 高级特性

<a name="resumable-download"></a>

##### 断点续下载

<a name="upload-file-for-not-found"></a>

##### 自定义 404 NotFound

<a name="file-management"></a>

### 文件管理

<a name="stat"></a>

#### 查看单个文件属性信息

<a name="copy"></a>

#### 复制单个文件

<a name="move"></a>

#### 移动单个文件

<a name="delete"></a>

#### 删除单个文件

<a name="batch"></a>

### 批量操作

<a name="batch-get"></a>

#### 批量获取文件属性信息


您可以调用资源表对象的 Stat() 方法并传入一个 Key（类似ID）来获取指定文件的相关信息。

    resp = rs.Stat(key)


如果请求成功，得到的 statRet 数组将会包含如下几个字段：

    hash: <FileETag>
    fsize: <FileSize>
    putTime: <PutTime>
    mimeType: <MimeType>

通过指定的操作行为名称，以及传入的一组 keys，可以达到批量处理的功能。

    resp = rs.Batch(actionNameString, keysList)

**示例**

批量获取文件属性信息：

    resp = rs.Batch('stat', [key1, key2, key3, ..., keyN])

批量获取下载链接：

    resp = rs.Batch('get', [key1, key2, key3, ..., keyN])

批量删除文件：

    resp = rs.Batch('delete', [key1, key2, key3, ..., keyN])

**响应**

**示例**

批量获取下载链接：

    resp = rs.BatchGet([key1, key2, key3, ..., keyN])

**响应**

    200 OK [
        <Result1>, <Result2>, ...
    ]
    298 Partial OK [
        <Result1>, <Result2>, ...
    ]
    <Result> 是 {
        code: <HttpCode>,
        data: <Data> 或 error: <ErrorMessage>
    }

当只有部分 keys 执行成功时，返回 298（PartialOK）。

<a name="batch-copy"></a>

#### 批量复制文件

<a name="batch-move"></a>

#### 批量移动文件

<a name="batch-delete"></a>

#### 批量删除文件

使用资源表对象的 `BatchDelete` 方法可以批量删除指定文件：

    resp = rs.BatchDelete(keysList)

**示例**

批量删除指定文件：

    resp = rs.BatchDelete([key1, key2, key3, ..., keyN])

**响应**

    200 OK [
        <Result1>, <Result2>, ...
    ]
    298 Partial OK [
        <Result1>, <Result2>, ...
    ]
    <Result> 是 {
        code: <HttpCode>,
        data: <Data> 或 error: <ErrorMessage>
    }

<a name="cloud-processing"></a>

### 云处理

<a name="image-processing"></a>

#### 图像

<a name="image-info"></a>

##### 查看图片属性信息

<a name="image-exif"></a>

##### 查看图片EXIF信息

<a name="image-mogrify-for-preview"></a>

##### 图像在线处理（缩略、裁剪、旋转、转化）

<a name="image-mogrify-for-save-as"></a>

##### 图像在线处理（缩略、裁剪、旋转、转化）后并持久化存储

<a name="Contributing"></a>

## 贡献代码


七牛云存储 Python SDK 源码地址：[https://github.com/qiniu/python-sdk](https://github.com/qiniu/python-sdk)

1. 登录 [github.com](https://github.com)
2. Fork [https://github.com/qiniu/python-sdk](https://github.com/qiniu/python-sdk)
3. 创建您的特性分支 (`git checkout -b my-new-feature`)
4. 提交您的改动 (`git commit -am 'Added some feature'`)
5. 将您的改动记录提交到远程 `git` 仓库 (`git push origin my-new-feature`)
6. 然后到 github 网站的该 `git` 远程仓库的 `my-new-feature` 分支下发起 Pull Request

<a name="License"></a>

## 许可证

Copyright (c) 2012 - 2013 qiniutek.com

基于 MIT 协议发布:

* [www.opensource.org/licenses/MIT](http://www.opensource.org/licenses/MIT)
