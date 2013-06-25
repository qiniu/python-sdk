## CHANGE LOG

### v6.0.1

2013-06-25 issue [#36](https://github.com/qiniu/python-sdk/pull/36)

- 加入CHANGELOG.md
- 更新文档
- 使config.UP_HOST="up.qiniu.com"
- 引入setup.py，并上传至PYPI

2013-06-24 issue [#35](https://github.com/qiniu/python-sdk/pull/35)

- 遵循 [sdkspec v6.0.1](https://github.com/qiniu/sdkspec/tree/v6.0.1)
  - 去除 fop.Call
  - 升级demo


2013-06-24 issue [#34](https://github.com/qiniu/python-sdk/pull/34)

- 遵循 [sdkspec v6.0.0](https://github.com/qiniu/sdkspec/tree/v6.0.0)
  - 增加 config.USER_AGENT 变量
- 修复单元测试，使用nosetests工具


2013-06-24 issue [#33](https://github.com/qiniu/python-sdk/pull/33)

- 增加了rsf的list_prefix功能


2013-06-24 issue [#31](https://github.com/qiniu/python-sdk/pull/31)

- 遵循 [sdkspec v1.0.2](https://github.com/qiniu/sdkspec/tree/v1.0.2)
  - rs.GetPolicy 删除 Scope，也就是不再支持批量下载的授权。
  - rs.New, PutPolicy.Token, GetPolicy.MakeRequest 增加 mac *digest.Mac 参数。

- 遵循 [sdkspec v1.0.1](https://github.com/qiniu/sdkspec/tree/v1.0.1)
  - io.GetUrl 改为 rs.MakeBaseUrl 和 rs.GetPolicy.MakeRequest
  - rs.PutPolicy 增加 ReturnUrl, ReturnBody, CallbackBody；将 Customer 改为 EndUser；删除 CallbackBodyType（只支持 form 格式） 

- 修复了imageView的bug
- 修正了demo



2013-06-24 issue [#28](https://github.com/qiniu/python-sdk/pull/28)

- 遵循 [sdkspec v1.0.3](https://github.com/qiniu/sdkspec/tree/v1.0.3)
  - io.PutExtra
    - Crc32 uint32
    - CheckCrc uint32 // CheckCrc == 0: 表示不进行 crc32 校验 // CheckCrc == 1: 对于 Put 等同于 CheckCrc = 2；对于 PutFile 会自动计算 crc32 值 // CheckCrc == 2: 表示进行 crc32 校验，且 crc32 值就是上面的 Crc32 变量
