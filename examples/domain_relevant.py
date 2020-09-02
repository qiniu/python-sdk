# -*- coding: utf-8 -*-
from qiniu import QiniuMacAuth, DomainManager
import json

"""域名上线"""

# 七牛账号的 公钥和私钥
access_key = "<access_key>"
secret_key = "<secret_key>"

auth = QiniuMacAuth(access_key, secret_key)

manager = DomainManager(auth)

# 域名
name = "zhuchangzhao2.peterpy.cn"

ret, res = manager.domain_online(name)

headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log}
print(json.dumps(headers, indent=4, ensure_ascii=False))
print(json.dumps(ret, indent=4, ensure_ascii=False))

"""域名下线"""

# 七牛账号的 公钥和私钥
access_key = "<access_key>"
secret_key = "<secret_key>"

auth = QiniuMacAuth(access_key, secret_key)

manager = DomainManager(auth)

# 域名
name = ""

ret, res = manager.domain_offline(name)

headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log}
print(json.dumps(headers, indent=4, ensure_ascii=False))
print(json.dumps(ret, indent=4, ensure_ascii=False))

"""删除域名"""

# 七牛账号的 公钥和私钥
access_key = "<access_key>"
secret_key = "<secret_key>"

auth = QiniuMacAuth(access_key, secret_key)

manager = DomainManager(auth)

# 域名
name = ""

ret, res = manager.delete_domain(name)

headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log}
print(json.dumps(headers, indent=4, ensure_ascii=False))
print(json.dumps(ret, indent=4, ensure_ascii=False))
