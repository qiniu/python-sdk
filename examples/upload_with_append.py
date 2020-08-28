from qiniu import Auth, urlsafe_base64_encode, append_file

# 七牛账号的公私钥
access_key = '<access_key>'
secret_key = '<secret_key>'

# 要上传的空间
bucket_name = ""

# 构建鉴权对象
q = Auth(access_key, secret_key)

key = "append.txt"

# 生成上传token，可以指定过期时间
token = q.upload_token(bucket_name)


def file2base64(localfile):
    with open(localfile, 'rb') as f:  # 以二进制读取文件
        data = f.read()
    return data


#  要追加的文本文件路径
localfile = ""

data = file2base64(localfile)

# 首次以追加方式上传文件时，offset设置为0；后续继续追加内容时需要传入上次追加成功后响应的"nextAppendPosition" :34  参数值。
offset = 0

encodekey = urlsafe_base64_encode(key)

ret, info = append_file(token, encodekey, data, offset)
print(ret)
print(info)
