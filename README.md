# Qiniu Python SDK
[![Software License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](LICENSE.md)
[![Build Status](https://travis-ci.org/qiniu/python-sdk.svg)](https://travis-ci.org/qiniu/python-sdk)
[![Latest Stable Version](https://badge.fury.io/co/Qiniu.png)](https://github.com/qiniu/python-sdk/releases)

## 安装

通过pip

```bash
pip install qiniu
```

## 运行环境

| Qiniu SDK版本 | Python 版本 |
|:--------------------:|:---------------------------:|
|          7.x         |          2.6, 2.7, 3.3, 3.4 |
|          6.x         |          2.6, 2.7 |

## 使用方法

```python
import qiniu
...
    q = qiniu.Auth(access_key, secret_key)
    key = 'hello'
    data = 'hello qiniu!'
    token = q.upload_token(bucket_name)
    ret, info = put_data(token, key, data)
    if ret is not None:
        print('All is OK')
    else:
        print(info) # error message in info
...
```

## 测试

``` bash
py.test
```

## 常见问题

- 第二个参数info保留了请求响应的信息，失败情况下ret 为none, 将info可以打印出来，提交给我们。
- API 的使用 demo 可以参考 [单元测试](https://github.com/qiniu/python-sdk/blob/master/test_qiniu.py)。

## 代码贡献

详情参考[代码提交指南](https://github.com/qiniu/python-sdk/blob/master/CONTRIBUTING.md)。

## 贡献记录

- [所有贡献者](https://github.com/qiniu/python-sdk/contributors)

## 联系我们

- 如果需要帮助，请提交工单（在portal右侧点击咨询和建议提交工单，或者直接向 support@qiniu.com 发送邮件）
- 如果有什么问题，可以到问答社区提问，[问答社区](http://qiniu.segmentfault.com/)
- 更详细的文档，见[官方文档站](http://developer.qiniu.com/)
- 如果发现了bug， 欢迎提交 [issue](https://github.com/qiniu/python-sdk/issues)
- 如果有功能需求，欢迎提交 [issue](https://github.com/qiniu/python-sdk/issues)
- 如果要提交代码，欢迎提交 pull request
- 欢迎关注我们的[微信](http://www.qiniu.com/#weixin) [微博](http://weibo.com/qiniutek)，及时获取动态信息。

## 代码许可

The MIT License (MIT).详情见 [License文件](https://github.com/qiniu/python-sdk/blob/master/LICENSE).
