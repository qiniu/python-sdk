# -*- coding:utf-8 -*-
import unittest
import os
from qiniu import fop

pic = "http://cheneya.qiniudn.com/hello_jpg"


class TestFop(unittest.TestCase):

    def test_exif(self):
        ie = fop.Exif()
        ret = ie.make_request(pic)
        self.assertEqual(ret, "%s?exif" % pic)

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
        ret = ii.make_request(pic)
        self.assertEqual(ret, "%s?imageInfo" % pic)


if __name__ == '__main__':
    unittest.main()
