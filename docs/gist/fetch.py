# coding=utf-8
import sys
sys.path.insert(0, "../../")

from base64 import urlsafe_b64encode as b64e
from qiniu.auth import digest

access_key = ""
secret_key = ""

src_url = ""
dest_bucket = ""
dest_key = ""

encoded_url = b64e(src_url)
dest_entry = "%s:%s" % (dest_bucket, dest_key)
encoded_entry = b64e(dest_entry)

api_host = "iovip.qbox.me"
api_path = "/fetch/%s/to/%s" % (encoded_url, encoded_entry)

mac = digest.Mac(access=access_key, secret=secret_key)
client = digest.Client(host=api_host, mac=mac)

ret, err = client.call(path=api_path)
if err is not None:
    print "failed"
    print err
else:
    print "success"
