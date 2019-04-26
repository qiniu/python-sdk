# -*- coding: utf-8 -*-
"""
异步抓取文件

https://developer.qiniu.com/kodo/api/1250/batch
"""
import requests
import json
from qiniu import QiniuMacAuth


access_key = ''
secret_key = ''

#生成鉴权QiniuToken
auth = QiniuMacAuth(access_key,secret_key)
body = json.dumps({

})
url = "http://api-z0.qiniu.com/sisyphus/fetch"
token = "Qiniu " + auth.token_of_request(method="POST",url = url,body=body,content_type="application/json")


header = {
    "Authorization":token,
    "Host":"api-<Zone>.qiniu.com",
    "Content-Type":"application/json"
}

response = requests.post(url,headers = header,data=body)
print(response.status_code,response.text)
