# -*- coding: utf-8 -*-
# flake8: noqa

import sys
from qiniu import QiniuMacAuth
from qiniu import AccountClient

access_key = sys.argv[1]
secret_key = sys.argv[2]

acc_client = AccountClient(QiniuMacAuth(access_key, secret_key))

ret, info = acc_client.list_apps()

print(ret)
print(info)

assert len(ret) is not None
