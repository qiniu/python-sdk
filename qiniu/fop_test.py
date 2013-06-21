import unittest
import os
import fop

pic = "http://cheneya.qiniudn.com/hello_jpg"
noexist_pic = "http://cheneya.qiniudn.com/noexist_pic" 

class TestFop(unittest.TestCase):
	def test_exif(self):
		ie = fop.Exif()
		ret, err = ie.call(pic)
		assert err is None
		assert ret is not None
		
		# error
		ret, err = ie.call(noexist_pic)
		assert err is not None
		assert ret is None

	def test_imageView(self):
		iv = fop.ImageView()
		iv.height = 100
		ret = iv.make_request(pic)
		self.assertEqual(ret, "%s?imageView/1/h/100" % pic)
		
		iv.quality = 20
		iv.format = "png"
		ret = iv.make_request(pic)
		self.assertEqual(ret, "%s?imageView/1/h/100/q/20/format/png" % pic)

	def test_imageInfo(self):
		ii = fop.ImageInfo()
		ret, err = ii.call(pic)
		assert err is None
		assert ret is not None
		
		# error
		ret, err = ii.call(noexist_pic)
		assert err is not None

	def test_imageMogr(self):
		im = fop.ImageMogr()
		im.auto_orient = True
		im.quality = 200
		im.rotate = 90
		target = "%s?imageMogr/auto-orient/quality/200/rotate/90" % pic
		self.assertEqual(im.make_request(pic), target)
	
if __name__ == '__main__':
	unittest.main()
