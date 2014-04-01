#coding:utf-8
import qiniu.conf
import qiniu.rs
import sys
host = "iovip.qbox.me"
bucket_name = "test-nba"
accesskey = "o8vfSdP-q0QvemJR1VihYLfslmznphvrj-0Vr-UD"
secertkey = "jor28vJUka_X6Pzut-U2MKG7Mk6NBCdgyfyLGp8Q" 

key = "upload123.gif"
url = "http://cdn0.sbnation.com/assets/4162335/noahgoat.gif"

qiniu.conf.ACCESS_KEY = accesskey
qiniu.conf.SECRET_KEY = secertkey
qiniu.conf.RS_HOST = host



if __name__ == "__main__":
    ret, err = qiniu.rs.Client().fetch(bucket_name, key, url)
    if err is not None:
        sys.stderr.write('error: %s ' % err)


    print ret
