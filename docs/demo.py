# -*- coding: utf-8 -*-
import os
import sys
import StringIO

# @gist import_io
import qiniu.io
# @endgist
import qiniu.conf
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
pic_key = None

# ----------------------------------------------------------

def setup(access_key, secret_key, bucketname, bucket_domain, pickey):
	global bucket_name, uptoken, key, key2, domain, key3, pic_key
	qiniu.conf.ACCESS_KEY = access_key
	qiniu.conf.SECRET_KEY = secret_key
	bucket_name = bucketname
	domain = bucket_domain
	pic_key = pickey
	# @gist uptoken
	policy = qiniu.rs.PutPolicy(bucket_name)
	uptoken = policy.token()
	# @endgist
	key = "python-demo-put-file"
	key2 = "python-demo-put-file-2"
	key3 = "python-demo-put-file-3"

def _setup():
	''' 根据环境变量配置信息 '''
	access_key = getenv("QINIU_ACCESS_KEY")
	if access_key is None:
		exit("请配置环境变量 QINIU_ACCESS_KEY")
	secret_key = getenv("QINIU_SECRET_KEY")
	bucket_name = getenv("QINIU_BUCKET_NAME")
	domain = getenv("QINIU_DOMAIN")
	pickey = getenv("QINIU_PIC_KEY")
	setup(access_key, secret_key, bucket_name, domain, pickey)

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
	base_url = qiniu.rs.make_base_url(domain, key)
	policy = qiniu.rs.GetPolicy()
	private_url = policy.make_request(base_url)
	# @endgist
	return private_url

def put_file():
	''' 演示上传文件的过程 '''
	# 尝试删除
	qiniu.rs.Client().delete(bucket_name, key)
	
	# @gist put_file
	localfile = "%s" % __file__

	ret, err = qiniu.io.put_file(uptoken, key, localfile)
	if err is not None:
		error(err)
		return
	# @endgist
	

def put_binary():
	''' 上传二进制数据 '''
	# 尝试删除
	qiniu.rs.Client().delete(bucket_name, key)
	
	# @gist put
	extra = qiniu.io.PutExtra()
	extra.mime_type = "text/plain"
	
	# data 可以是str或read()able对象
	data = StringIO.StringIO("hello!")
	ret, err = qiniu.io.put(uptoken, key, data, extra)
	if err is not None:
		error(err)
		return
	# @endgist

def resumable_put():
	''' 断点续上传 '''
	# 尝试删除
	qiniu.rs.Client().delete(bucket_name, key)
	
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
	qiniu.rs.Client().delete(bucket_name, key)
	
	# @gist resumable_put_file
	localfile = "%s" % __file__
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
	ret, err = qiniu.rs.Client().stat(bucket_name, key)
	if err is not None:
		error(err)
		return
	print ret,
	# @endgist

def copy():
	''' 复制文件 '''
	# 初始化
	qiniu.rs.Client().delete(bucket_name, key2)
	
	# @gist copy
	ret, err = qiniu.rs.Client().copy(bucket_name, key, bucket_name, key2)
	if err is not None:
		error(err)
		return
	# @endgist
	
	stat, err = qiniu.rs.Client().stat(bucket_name, key2)
	if err is not None:
		error(err)
		return
	print 'new file:', stat,

def move():
	''' 移动文件 '''
	# 初始化
	qiniu.rs.Client().delete(bucket_name, key3)
	
	# @gist move
	ret, err = qiniu.rs.Client().move(bucket_name, key2, bucket_name, key3)
	if err is not None:
		error(err)
		return
	# @endgist
	
	# 查看文件是否移动成功
	ret, err = qiniu.rs.Client().stat(bucket_name, key3)
	if err is not None:
		error(err)
		return
	
	# 查看文件是否被删除
	ret, err = qiniu.rs.Client().stat(bucket_name, key2)
	if err is None:
		error("删除失败")
		return

def delete():
	''' 删除文件 '''
	# @gist delete
	ret, err = qiniu.rs.Client().delete(bucket_name, key3)
	if err is not None:
		error(err)
		return
	# @endgist
	
	ret, err = qiniu.rs.Client().stat(bucket_name, key3)
	if err is None:
		error("删除失败")
		return

def image_info():
	''' 查看图片的信息 '''
	
	# @gist image_info
	# 生成base_url
	url = qiniu.rs.make_base_url(domain, pic_key)

	# 生成fop_url
	image_info = qiniu.fop.ImageInfo()
	url = image_info.make_request(url)

	# 对其签名，生成private_url。如果是公有bucket此步可以省略
	policy = qiniu.rs.GetPolicy()
	url = policy.make_request(url)

	print '可以在浏览器浏览: %s' % url
	# @endgist

def image_exif():
	''' 查看图片的exif信息 '''
	# @gist exif
	# 生成base_url
	url = qiniu.rs.make_base_url(domain, pic_key)

	# 生成fop_url
	image_exif = qiniu.fop.Exif()
	url = image_exif.make_request(url)

	# 对其签名，生成private_url。如果是公有bucket此步可以省略
	policy = qiniu.rs.GetPolicy()
	url = policy.make_request(url)

	print '可以在浏览器浏览: %s' % url
	# @endgist

def image_view():
	''' 对图片进行预览处理 '''
	# @gist image_view
	iv = qiniu.fop.ImageView()
	iv.width = 100

	# 生成base_url
	url = qiniu.rs.make_base_url(domain, pic_key)
	# 生成fop_url
	url = iv.make_request(url)
	# 对其签名，生成private_url。如果是公有bucket此步可以省略
	policy = qiniu.rs.GetPolicy()
	url = policy.make_request(url)
	print '可以在浏览器浏览: %s' % url
	# @endgist

def batch():
	''' 文件处理的批量操作 '''
	# @gist batch_path
	path_1 = qiniu.rs.EntryPath(bucket_name, key)
	path_2 = qiniu.rs.EntryPath(bucket_name, key2)
	path_3 = qiniu.rs.EntryPath(bucket_name, key3)
	# @endgist
	
	# 查看状态
	# @gist batch_stat
	rets, err = qiniu.rs.Client().batch_stat([path_1, path_2, path_3])
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
	rets, err = qiniu.rs.Client().batch_copy([pair_1])
	if not rets[0]['code'] == 200:
		error("复制失败")
		return
	# @endgist
	
	qiniu.rs.Client().batch_delete([path_2])
	# @gist batch_move
	pair_2 = qiniu.rs.EntryPathPair(path_3, path_2)
	rets, err = qiniu.rs.Client().batch_move([pair_2])
	if not rets[0]['code'] == 200:
		error("移动失败")
		return
	# @endgist
	
	# 删除残留文件
	# @gist batch_delete
	rets, err = qiniu.rs.Client().batch_delete([path_1, path_2])
	if not [ret['code'] for ret in rets] == [200, 200]:
		error("删除失败")
		return
	# @endgist

def list_prefix():
	''' 列出文件操作 '''
	# @gist list_prefix
	rets, err = qiniu.rsf.Client().list_prefix(bucket_name, prefix="test", limit=2)
	if err is not None:
		error(err)
		return
	print rets
	
	# 从上一次list_prefix的位置继续列出文件
	rets2, err = qiniu.rsf.Client().list_prefix(bucket_name, prefix="test", limit=1, marker=rets['marker'])
	if err is not None:
		error(err)
		return
	print rets2
	# @endgist

if __name__ == "__main__":
	_setup()
	
	demos = get_demo_list()
	run_demos(demos)
