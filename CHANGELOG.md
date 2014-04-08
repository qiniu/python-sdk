## CHANGE LOG

### v6.1.5

2014-04-08 issue [#98](https://github.com/qiniu/python-sdk/pull/98)

- [#98] 增加fetch、prefetch、pfop三个接口的范例代码

### v6.1.4

2014-03-28 issue [#95](https://github.com/qiniu/python-sdk/pull/95)

- [#78] 增加 putpolicy 选项:saveKey,insertOnly,detectMime,fsizeLimit,persistentNotifyUrl,persistentOps
- [#80] 增加 gettoken 过期时间参数，增加 rsf 返回为空的EOF判断
- [#86] 修正 断点续传的bug
- [#93] 修正 4M 分块计算bug
- [#96] 修正 mime_type typo

### v6.1.3

2013-10-24 issue [#77](https://github.com/qiniu/python-sdk/pull/77)

- bug fix, httplib_thunk.py 中的无效符号引用
- PutPolicy：增加 saveKey、persistentOps/persistentNotifyUrl、fsizeLimit（文件大小限制）等支持
- 断点续传：使用新的 mkfile 协议


### v6.1.2

2013-08-01 issue [#66](https://github.com/qiniu/python-sdk/pull/66)

- 修复在Windows环境下put_file无法读取文件的bug
- 修复在Windows环境下创建临时文件的权限问题
- 修复在Windows环境下对二进制文件计算crc32的bug


### v6.1.1

2013-07-05 issue [#60](https://github.com/qiniu/python-sdk/pull/60)

- 整理文档


### v6.1.0

2013-07-03 issue [#58](https://github.com/qiniu/python-sdk/pull/58)

- 实现最新版的上传API，<http://docs.qiniu.com/api/put.html>
	- io.PutExtra更新，废弃callback_params，bucket，和custom_meta，新增params
- 修复[#16](https://github.com/qiniu/python-sdk/issues/16)
	- put接口可以传入类文件对象（file-like object）
- 修复[#52](https://github.com/qiniu/python-sdk/issues/52)


### v6.0.1

2013-06-27 issue [#43](https://github.com/qiniu/python-sdk/pull/43)

- 遵循 [sdkspec v6.0.2](https://github.com/qiniu/sdkspec/tree/v6.0.2)
	- 现在，rsf.list_prefix在没有更多数据时，err 会返回 rsf.EOF


### v6.0.0

2013-06-26 issue [#42](https://github.com/qiniu/python-sdk/pull/42)

- 遵循 [sdkspec v6.0.1](https://github.com/qiniu/sdkspec/tree/v6.0.1)
