# -*- coding:utf-8 -*-
import json


class Exif(object):

    def make_request(self, url):
        return '%s?exif' % url


class ImageView(object):
    mode = 1  # 1或2
    width = None  # width 默认为0，表示不限定宽度
    height = None
    quality = None  # 图片质量, 1-100
    format = None  # 输出格式, jpg, gif, png, tif 等图片格式

    def make_request(self, url):
        target = []
        target.append('%s' % self.mode)

        if self.width is not None:
            target.append("w/%s" % self.width)

        if self.height is not None:
            target.append("h/%s" % self.height)

        if self.quality is not None:
            target.append("q/%s" % self.quality)

        if self.format is not None:
            target.append("format/%s" % self.format)

        return "%s?imageView/%s" % (url, '/'.join(target))


class ImageInfo(object):

    def make_request(self, url):
        return '%s?imageInfo' % url
