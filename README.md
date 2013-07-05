Qiniu Resource Storage SDK for Python
===

[![Build Status](https://api.travis-ci.org/qiniu/python-sdk.png?branch=develop)](https://travis-ci.org/qiniu/python-sdk)

[![Qiniu Logo](http://qiniutek.com/images/logo-2.png)](http://qiniu.com/)

## 使用

参考文档：[七牛云存储 Python SDK 使用指南](https://github.com/qiniu/python-sdk/blob/develop/docs/README.md)

## 单元测试

1. 您需要拥有一对有效的 Access Key 和 Secret Key 用来进行签名认证。可以通过如下步骤获得：

	1. [开通七牛开发者帐号](https://portal.qiniu.com/signup)
	2. [登录七牛开发者自助平台，查看 Access Key 和 Secret Key](https://portal.qiniu.com/setting/key) 。
	3. 在开发者后台新建一个空间

	然后将在`test-env.sh`中填入相关信息。
2. 需安装[nosetests](https://nose.readthedocs.org/en/latest/)测试工具。

运行测试：

	source test-env.sh
	nosetests

## 贡献代码

1. Fork
2. 创建您的特性分支 (`git checkout -b my-new-feature`)
3. 提交您的改动 (`git commit -am 'Added some feature'`)
4. 将您的修改记录提交到远程 `git` 仓库 (`git push origin my-new-feature`)
5. 然后到 github 网站的该 `git` 远程仓库的 `my-new-feature` 分支下发起 Pull Request

## 许可证

Copyright (c) 2013 qiniu.com

基于 MIT 协议发布:

* [www.opensource.org/licenses/MIT](http://www.opensource.org/licenses/MIT)
