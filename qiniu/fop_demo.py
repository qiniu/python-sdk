import unittest
import os
import fop

access_key = os.getenv("QINIU_ACCESS_KEY")
secret_key = os.getenv("QINIU_SECRET_KEY")
pic = os.getenv("QINIU_TEST_PIC_1")
noexist_pic = os.getenv("QINIU_NOEXIST_PIC")

class TestFop(unittest.TestCase):
	def test_imageExif(self):
		ie = fop.ImageExif()
		ret, err = ie.call(pic)
		self.assertIsNone(err)
		self.assertIsNotNone(ret)
		
		# error
		ret, err = ie.call(noexist_pic)
		self.assertIsNotNone(err)
		self.assertIsNone(ret)

	def test_imageView(self):
		iv = fop.ImageView()
		iv.height = 100
		ret = iv.make_request(pic)
		self.assertEqual(ret, "%s?imageView/1/h/100/" % pic)
		
		iv.quality = 20
		iv.format = "png"
		ret = iv.make_request(pic)
		self.assertEqual(ret, "%s?imageView/1/h/100/q/20/format/png/" % pic)

	def test_imageInfo(self):
		ii = fop.ImageInfo()
		ret, err = ii.call(pic)
		self.assertIsNone(err)
		self.assertIsNotNone(ret)
		
		# error
		ret, err = ii.call(noexist_pic)
		self.assertIsNotNone(err)

	def test_imageMogr(self):
		im = fop.ImageMogr()
		im.auto_orient = True
		im.quality = 200
		im.rotate = 90
		target = "%s?imageMogr/auto-orient/quality/200/rotate/90" % pic
		self.assertEqual(im.make_request(pic), target)
	
if __name__ == '__main__':
	unittest.main()
