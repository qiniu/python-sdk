# -*- coding: utf-8 -*-
import os
import sys

# @gist import_io
import qiniu.io
# @endgist
import qiniu.config
# @gist import_token
import qiniu.auth_token
# @endgist
# @gist import_rs
import qiniu.rs
# @endgist
# @gist import_fop
import qiniu.fop
# @endgist
# @gist import_resumable_io
import qiniu.resumable_io as rio
# @endgist
# @gist import_rsf
import qiniu.rsf
# @endgist

bucket_name = None
uptoken = None
key = None
key2 = None
key3 = None
domain = None
rs_client = None

# ----------------------------------------------------------

def setup(access_key, secret_key, bucketname, bucket_domain):
	global bucket_name, uptoken, key, key2, domain, key3, rs_client
	qiniu.config.ACCESS_KEY = access_key
	qiniu.config.SECRET_KEY = secret_key
	bucket_name = bucketname
	domain = bucket_domain
	# @gist uptoken
	policy = qiniu.auth_token.PutPolicy(bucket_name)
	uptoken = policy.token()
	# @endgist
	key = "python-demo-put-file"
	key2 = "python-demo-put-file-2"
	key3 = "python-demo-put-file-3"
	rs_client = qiniu.rs.Rs()

def _setup():
	''' 根据环境变量配置信息 '''
	access_key = getenv("QINIU_ACCESS_KEY")
	if access_key is None:
		exit("请配置环境变量 QINIU_ACCESS_KEY")
	secret_key = getenv("QINIU_SECRET_KEY")
	bucket_name = getenv("QINIU_BUCKET_NAME")
	domain = getenv("QINIU_DOMAIN")
	setup(access_key, secret_key, bucket_name, domain)

def getenv(name):
	env = os.getenv(name)
	if env is None:
		sys.stderr.write("请配置环境变量 %s\n" % name)
		exit(1)
	return env

def error(obj):
	sys.stderr.write('error: %s ' % obj)

def get_demo_list():
	return [put_file, put_binary,
			resumable_put, resumable_put_file,
			stat, copy, move, delete, batch,
			image_info, image_exif, image_view,
			list_prefix,
	]

def run_demos(demos):
	for i, demo in enumerate(demos):
		print '%s.%s ' % (i+1, demo.__doc__),
		demo()
		print

# ----------------------------------------------------------
def make_private_url(domain, key):
	''' 生成私有下载链接 '''
	# @gist dntoken
	base_url = qiniu.auth_token.make_base_url(domain, key)
	policy = qiniu.auth_token.GetPolicy()
	private_url = policy.make_request(base_url)
	# @endgist
	return private_url

def put_file():
	''' 演示上传文件的过程 '''
	# 尝试删除
	rs_client.delete(bucket_name, key)
	
	# @gist put_file
	localfile = "./%s" % __file__
	extra = qiniu.io.PutExtra(bucket_name)
	
	ret, err = qiniu.io.put_file(uptoken, key, localfile, extra)
	if err is not None:
		error(err)
		return
	# @endgist
	

def put_binary():
	''' 上传二进制数据 '''
	# 尝试删除
	rs_client.delete(bucket_name, key)
	
	# @gist put
	extra = qiniu.io.PutExtra(bucket_name)
	extra.mime_type = "text/plain"
	
	ret, err = qiniu.io.put(uptoken, key, "hello!", extra)
	if err is not None:
		error(err)
		return
	# @endgist

def resumable_put():
	''' 断点续上传 '''
	# 尝试删除
	rs_client = qiniu.rs.Rs()
	rs_client.delete(bucket_name, key)
	
	# @gist resumable_put
	class ResumableUpload(object):
		position = 0
		def __init__(self, string_data):
			self.data = string_data
		
		def read(self, length):
			data = self.data[self.position: self.position+length]
			self.position += length
			return data

	a = "resumable upload string"
	extra = rio.PutExtra(bucket_name)
	extra.mime_type = "text/plain"
	ret, err = rio.put(uptoken, key, ResumableUpload(a), len(a), extra)
	if err is not None:
		error(err)
		return
	print ret,
	# @endgist
	

def resumable_put_file():
	''' 断点续上传文件 '''
	# 尝试删除
	rs_client.delete(bucket_name, key)
	
	# @gist resumable_put_file
	localfile = "./%s" % __file__
	extra = rio.PutExtra(bucket_name)
	
	ret, err = rio.put_file(uptoken, key, localfile, extra)
	if err is not None:
		error(err)
		return
	print ret,
	# @endgist
	

def stat():
	''' 查看上传文件的内容 '''
	# @gist stat
	ret, err = rs_client.stat(bucket_name, key)
	if err is not None:
		error(err)
		return
	print ret,
	# @endgist

def copy():
	''' 复制文件 '''
	# 初始化
	rs_client.delete(bucket_name, key2)
	
	# @gist copy
	ret, err = rs_client.copy(bucket_name, key, bucket_name, key2)
	if err is not None:
		error(err)
		return
	# @endgist
	
	stat, err = rs_client.stat(bucket_name, key2)
	if err is not None:
		error(err)
		return
	print 'new file:', stat,

def move():
	''' 移动文件 '''
	# 初始化
	rs_client.delete(bucket_name, key3)
	
	# @gist move
	ret, err = rs_client.move(bucket_name, key2, bucket_name, key3)
	if err is not None:
		error(err)
		return
	# @endgist
	
	# 查看文件是否移动成功
	ret, err = rs_client.stat(bucket_name, key3)
	if err is not None:
		error(err)
		return
	
	# 查看文件是否被删除
	ret, err = rs_client.stat(bucket_name, key2)
	if err is None:
		error("删除失败")
		return

def delete():
	''' 删除文件 '''
	# @gist delete
	ret, err = rs_client.delete(bucket_name, key3)
	if err is not None:
		error(err)
		return
	# @endgist
	
	ret, err = rs_client.stat(bucket_name, key3)
	if err is None:
		error("删除失败")
		return

def image_info():
	''' 上传图片, 并且查看他的信息 '''
	# 初始化
	rs_client.delete(bucket_name, key2)
	
	extra = qiniu.io.PutExtra(bucket_name)
	extra.mime_type = "image/png"
	localfile = './demo-photo.jpeg'
	ret, err = qiniu.io.put_file(uptoken, key2, localfile, extra)
	if err is not None:
		error(err)
		return

	# @gist image_info
	base_url = qiniu.auth_token.make_base_url(domain, key2)
	info, err = qiniu.fop.ImageInfo().call(base_url)
	if err is not None:
		error(err)
		return
	print info,
	# @endgist

def image_exif():
	''' 查看图片的exif信息 '''
	# @gist exif
	base_url = qiniu.auth_token.make_base_url(domain, key2)
	exif, err = qiniu.fop.Exif().call(base_url)
	if err is not None:
		# 部分图片不存在exif
		if not err == "no exif data":
			error(err)
		return
	print exif
	# @endgist

def image_view():
	''' 对图片进行预览处理 '''
	# @gist image_view
	iv = qiniu.fop.ImageView()
	iv.width = 100
	base_url = qiniu.auth_token.make_base_url(domain, key2)
	print '可以在浏览器浏览: %s' % iv.make_request(base_url)
	# @endgist

def batch():
	''' 文件处理的批量操作 '''
	rs_client = qiniu.rs.Rs()
	# @gist batch_path
	path_1 = qiniu.rs.EntryPath(bucket_name, key)
	path_2 = qiniu.rs.EntryPath(bucket_name, key2)
	path_3 = qiniu.rs.EntryPath(bucket_name, key3)
	# @endgist
	
	# 查看状态
	# @gist batch_stat
	rets, err = rs_client.batch_stat([path_1, path_2, path_3])
	if err is not None:
		error(err)
		return
	# @endgist
	if not [ret['code'] for ret in rets] == [200, 612, 612]:
		error("批量获取状态与预期不同")
		return
	
	# 复制
	# @gist batch_copy
	pair_1 = qiniu.rs.EntryPathPair(path_1, path_3)
	rets, err = rs_client.batch_copy([pair_1])
	if not rets[0]['code'] == 200:
		error("复制失败")
		return
	# @endgist
	
	rs_client.batch_delete([path_2])
	# @gist batch_move
	pair_2 = qiniu.rs.EntryPathPair(path_3, path_2)
	rets, err = rs_client.batch_move([pair_2])
	if not rets[0]['code'] == 200:
		error("移动失败")
		return
	# @endgist
	
	# 删除残留文件
	# @gist batch_delete
	rets, err = rs_client.batch_delete([path_1, path_2])
	if not [ret['code'] for ret in rets] == [200, 200]:
		error("删除失败")
		return
	# @endgist

def list_prefix():
	''' 列出文件操作 '''
	# @gist list_prefix
	rsf_client = qiniu.rsf.Rsf()
	rets, err = rsf_client.list_prefix(bucket_name, prefix="python-demo-put-file")
	if err is not None:
		error(err)
		return
	print rets,
	# @endgist

if __name__ == "__main__":
	_setup()
	
	demos = get_demo_list()
	run_demos(demos)
