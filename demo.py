# -*- coding: utf-8 -*-
import os

import qiniu.io
import qiniu.config
import qiniu.auth_token
import qiniu.rs
import qiniu.fop

bucket_name = None
uptoken = None
key = None
key2 = None
key3 = None
domain = None
rs_client = qiniu.rs.Rs()

# ----------------------------------------------------------

def _setup():
	''' 配置信息 '''
	global bucket_name, uptoken, key, key2, domain, key3
	qiniu.config.ACCESS_KEY = os.getenv("QINIU_ACCESS_KEY")
	qiniu.config.SECRET_KEY = os.getenv("QINIU_SECRET_KEY")
	bucket_name = os.getenv("QINIU_BUCKET_NAME")
	domain = os.getenv("QINIU_DOMAIN")
	policy = qiniu.auth_token.PutPolicy(bucket_name)
	uptoken = policy.token()
	key = "python-demo-put-file"
	key2 = "python-demo-put-file-2"
	key3 = "python-demo-put-file-3"

def _error(obj):
	print 'error: %s' % obj,

def _get_demo_list():
	return [put_file, put_binary, stat, copy, move, delete, 
			image_info, image_exif, image_view, batch]

def _run_demos(demos):
	for i, demo in enumerate(demos):
		print '%s.%s ' % (i+1, demo.__doc__),
		demo()
		print

# ----------------------------------------------------------

def put_file():
	''' 演示上传文件的过程 '''
	localfile = "./%s" % __file__
	extra = qiniu.io.PutExtra()

	# 尝试删除
	rs_client.delete(bucket_name, key)
	ret, err = qiniu.io.put_file(uptoken, bucket_name, key, localfile, extra)
	if err is not None:
		_error(err)
		return
	
	# 删除生成的文件
	rs_client.delete(bucket_name, key)

def put_binary():
	''' 上传二进制数据 '''
	extra = qiniu.io.PutExtra()
	extra.mime_type = "text/plain"
	
	ret, err = qiniu.io.put(uptoken, bucket_name, key, "hello!", extra)
	if err is not None:
		_error(err)
		return

def stat():
	''' 查看上传文件的内容 '''
	ret, err = rs_client.stat(bucket_name, key)
	if err is not None:
		_error(err)
		return
	print ret,

def copy():
	''' 复制文件 '''
	# 初始化
	rs_client.delete(bucket_name, key2)
	
	ret, err = rs_client.copy(bucket_name, key, bucket_name, key2)
	if err is not None:
		_error(err)
		return

	stat, err = rs_client.stat(bucket_name, key2)
	if err is not None:
		_error(err)
		return
	print 'new file:', stat,

def move():
	''' 移动文件 '''
	# 初始化
	rs_client.delete(bucket_name, key3)
	
	ret, err = rs_client.move(bucket_name, key2, bucket_name, key3)
	if err is not None:
		_error(err)
		return
	
	# 查看文件是否移动成功
	ret, err = rs_client.stat(bucket_name, key3)
	if err is not None:
		_error(err)
		return
	
	# 查看文件是否被删除
	ret, err = rs_client.stat(bucket_name, key2)
	if err is None:
		_error("删除失败")
		return

def delete():
	''' 删除文件 '''
	ret, err = rs_client.delete(bucket_name, key3)
	if err is not None:
		_error(err)
		return
	
	ret, err = rs_client.stat(bucket_name, key3)
	if err is None:
		_error("删除失败")
		return

def image_info():
	''' 上传图片, 并且查看他的信息 '''
	# 初始化
	rs_client.delete(bucket_name, key2)
	
	extra = qiniu.io.PutExtra()
	extra.mime_type = "image/png"
	localfile = './demo-pic.jpg'
	ret, err = qiniu.io.put_file(uptoken, bucket_name, key2, localfile, extra)
	if err is not None:
		_error(err)
		return

	info, err = qiniu.fop.ImageInfo().call(domain + key2)
	if err is not None:
		_error(err)
		return 
	print info,

def image_exif():
	''' 查看图片的exif信息 '''
	exif, err = qiniu.fop.ImageExif().call(domain + key2)
	if err is not None:
		_error(err)
		return
	print exif

def image_view():
	''' 对图片进行预览处理 '''
	iv = qiniu.fop.ImageView()
	iv.width = 200
	print '可以在浏览器浏览: %s' % iv.make_request(domain + key2)

def batch():
	''' 文件处理的批量操作 '''
	path_1 = qiniu.rs.EntryPath(bucket_name, key)
	path_2 = qiniu.rs.EntryPath(bucket_name, key2)
	path_3 = qiniu.rs.EntryPath(bucket_name, key3)
	
	# 查看状态
	rets, err = rs_client.batch_stat([path_1, path_2, path_3])
	if err is not None:
		_error(err)
		return
	if not [ret['code'] for ret in rets] == [200, 200, 612]:
		_error("批量获取状态与预期不同")
		return
	
	# 复制
	pair_1 = qiniu.rs.EntryPathPair(path_1, path_3)
	rets, err = rs_client.batch_copy([pair_1])
	if not rets[0]['code'] == 200:
		_error("复制失败")
		return
	
	# 删除残留文件
	rets, err = rs_client.batch_delete([path_1, path_2, path_3])
	if not [ret['code'] for ret in rets] == [200, 200, 200]:
		_error("删除失败")
		return
	

if __name__ == "__main__":
	_setup()

	demos = _get_demo_list()
	_run_demos(demos)
