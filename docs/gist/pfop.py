#coding=utf-8
import sys
sys.path.insert(0, "../../")

from urllib import quote
from qiniu.auth import digest

access_key = ""
secret_key = ""

bucket = ""
key = ""
fops = ""
notify_url = ""
force = False

api_host = "api.qiniu.com"
api_path = "/pfop/"
body = "bucket=%s&key=%s&fops=%s&notifyURL=%s" % \
       (quote(bucket), quote(key), quote(fops), quote(notify_url))

body = "%s&force=1" % (body,) if force is not False else body

content_type = "application/x-www-form-urlencoded"
content_length = len(body)

mac = digest.Mac(access=access_key, secret=secret_key)
client = digest.Client(host=api_host, mac=mac)

ret, err = client.call_with(path=api_path, body=body,
                            content_type=content_type, content_length=content_length)
if err is not None:
    print "failed"
    print err
else:
    print "success"
    print ret