---
title: Python 2.x SDK | 七牛云存储
---

# Python 2.x SDK 使用指南


此 SDK 适用于 Python 2.x 版本

**OAuth2.0 认证**

- [应用接入](#acc-appkey)
- [登录授权](#acc-login)

**云存储接口**

- [新建资源表](#rs-NewService)
- [获得上传授权](#rs-PutAuth)
- [上传文件](#rs-PutFile)
- [获取已上传文件信息](#rs-Stat)
- [下载文件](#rs-Get)
- [发布公开资源](#rs-Publish)
- [取消资源发布](#rs-Unpublish)
- [删除已上传的文件](#rs-Delete)
- [删除整张资源表](#rs-Drop)
- [资源表批量操作接口](#rs-Batch)
- [批量下载](#rs-BatchGet)
- [批量删除](#rs-BatchDelete)

## OAuth 2.0 认证

<a name="acc-appkey"></a>

### 1. 应用接入

您可以解压 SDK 包后进入到 qbox/ 目录，选择和修改应用接入所需要使用的配置文件。在 qbox/ 目录中，您可以看到已经存在的3个配置文件，它们是：config.locla.py, config.dev.py 和 config.pro.py，分别对应本机测试环境，七牛云存储测试服务器环境（沙箱）和七牛云存储正式线上环境。您可以根据实际需要以此为模板新建或者链接一个名为 config.py 的文件即可，例如：

    cd ./qbox
    ln -s config.pro.py config.py # 或 cp config.pro.py config.py

也可以用 qbox/ 目录下的 switch 命令行工具一键切换：

    ./switch pro # 这样等价于 ln -s config.pro.py config.py

然后，您可以根据实际情况修改 config.py 文件里边的 **CLIENT_ID** 和 **CLIENT_SECRET** 的值（SDK中缺省值可供您试用阶段调试，无需修改）。

<a name="acc-login"></a>

### 2. 登录授权

除了您的应用程序需要有 ClientId 和 ClientSecret 进行授权，您还需要有一个七牛云存储的帐号用来登录，登录授权后所有上传至七牛云存储的资源都会和该帐号建立关联。
如下例子，进行登录授权：

    client = simpleoauth2.Client()
    client.ExchangeByPassword('test@qbox.net', 'test')


登录成功后，服务端会返回一段JSON（SDK以Array保存结果），包含字段 access_token, refresh_token 和 expires_in；
access_token 是一个已授权的凭证，用于后续访问云存储和图像处理接口等；
refresh_token 用于当 access_token 失效后重新获取新的 access_token；
expires_in 是 access_token 的有效期。

## 云存储接口

<a name="rs-NewService"></a>

### 1. 新建资源表

新建资源表的意义在于，您可以将所有上传的资源分布式加密存储在七牛云存储服务端后还能保持相应的完整映射索引。

    tblName = 'tblName'
    rs = qboxrs.Service(client, tblName)


<a name="rs-PutAuth"></a>

### 2. 获得上传授权

建完资源表，在上传文件并和该资源表建立关联之前，还需要取得上传授权。所谓上传授权，就是获得一个可匿名直传的且离客户端应用程序最近的一个云存储节点的临时有效URL。
要取得上传授权，只需调用已经实例化好的资源表对象的 PutAuth() 方法。实例代码如下：

    resp = rs.PutAuth()


如果请求成功，putAuthRet 会包含 url 和 expires_in 两个字段。url 字段对应的值为匿名上传的临时URL，expires_in 对应的值则是该临时URL的有效期。

<a name="rs-PutFile"></a>

### 3. 上传文件

一旦建立好资源表和取得上传授权，就可以开始上传文件了。只需调用sdk提供的 PutFile() 方法即可。示例代码如下：

    resp = rscli.PutFile(resp['url'], tblName, key, mimeType, filePath, 'CustomData', {'key': key}, True)

最后一个参数值为 `True` 表示针对该文件上传启用 crc32 数据校验，该值默认是 `False` 。


<a name="rs-Stat"></a>

### 4. 获取已上传文件信息

您可以调用资源表对象的 Stat() 方法并传入一个 Key（类似ID）来获取指定文件的相关信息。

    resp = rs.Stat(key)


如果请求成功，得到的 statRet 数组将会包含如下几个字段：

    hash: <FileETag>
    fsize: <FileSize>
    putTime: <PutTime>
    mimeType: <MimeType>


<a name="rs-Get"></a>

### 5. 下载文件

要下载一个文件，首先需要取得下载授权，所谓下载授权，就是取得一个临时合法有效的下载链接，只需调用资源表对象的 Get() 方法并传入相应的 文件ID 和下载要保存的文件名 作为参数即可。示例代码如下：

    resp = rs.Get(key, key)


注意，这并不会直接将文件下载并命名为一个 example.jpg 的文件。当请求执行成功，Get() 方法返回的 getRet 变量将会包含如下字段：

    url: <DownloadURL> # 获取文件内容的实际下载地址
    hash: <FileETag>
    fsize: <FileSize>
    mimeType: <MimeType>
    expires:<Seconds> ＃下载url的实际生命周期，精确到秒


这里所说的断点续传指断点续下载，所谓断点续下载，就是已经下载的部分不用下载，只下载基于某个“游标”之后的那部分文件内容。相对于资源表对象的 Get() 方法，调用断点续下载方法 GetIfNotModified() 需额外再传入一个 $baseVersion 的参数作为下载的内容起点。示例代码如下：

    resp = rs.GetIfNotModified(key, key, resp['hash'])

GetIfNotModified() 方法返回的结果包含的字段同 Get() 方法一致。

<a name="rs-Publish"></a>

### 6. 发布公开资源

使用七牛云存储提供的资源发布功能，您可以将一个资源表里边的所有文件以静态链接可访问的方式公开发布到您自己的域名下。
要公开发布一个资源表里边的所有文件，只需调用改资源表对象的 Publish() 方法并传入 域名 作为参数即可。如下示例：

    resp = rs.Publish(YOUR_DOMAIN)

注意：需要到您的域名管理中心将 YOUR_DOMAIN CNAME 到 iovip.qbox.me

如果还没有您自己的域名，可将 YOUR_DOMAIN 改成 iovip.qbox.me/tblName 供临时测试使用。

<a name="rs-Unpublish"></a>

### 7. 取消资源发布

调用资源表对象的 Unpublish() 方法可取消该资源表内所有文件的静态外链。

    resp = rs.Unpublish(YOUR_DOMAIN)

<a name="rs-Delete"></a>

### 8. 删除已上传的文件

要删除指定的文件，只需调用资源表对象的 Delete() 方法并传入 文件ID（key）作为参数即可。如下示例代码：

    resp = rs.Delete(key)

<a name="rs-Drop"></a>

### 9. 删除整张资源表

要删除整个资源表及该表里边的所有文件，可以调用资源表对象的 Drop() 方法。
需慎重，这会删除整个表及其所有文件

    resp = rs.Drop()


<a name="rs-Batch"></a>

### 10. 资源表批量操作接口

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


<a name="rs-BatchGet"></a>

### 11. 批量下载

使用资源表对象的 `BatchGet` 方法可以批量取得下载链接：

    resp = rs.BatchGet(keysList)

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


<a name="rs-BatchDelete"></a>

### 12. 批量删除

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

当只有部分 keys 执行成功时，返回 298（PartialOK）。

