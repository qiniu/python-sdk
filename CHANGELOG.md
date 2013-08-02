## CHANGE LOG

### v6.1.2

2013-08-01 issue [#63](https://github.com/qiniu/python-sdk/pull/63) [#64](https://github.com/qiniu/python-sdk/pull/64)

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
