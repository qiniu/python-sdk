# -*- encoding: utf-8 -*-

from base64 import urlsafe_b64encode

def MakeStyleURL(url, templPngFile, params, quality = 85):
    """
     * func MakeStyleURL(url string, templPngFile string, params string, quality int) => (urlMakeStyle string)
    """
    return url + '/makeStyle/' + urlsafe_b64encode(templPngFile) + '/params/' + urlsafe_b64encode(params) + '/quality/' + quality

def ImagePreviewURL(url, thumbType):
    """
     * func ImagePreviewURL(url string, thumbType int) => (urlImagePreview string)
    """
    return url + '/imagePreview/' + thumbType

def ImageMogrURL(url, params):
    """
     * func ImagePreviewURL(url string, thumbType int) => (urlImagePreview string)
    """
    return url + '/imageMogr/' + params

def ImageInfoURL(url):
    """
     * func ImageInfoURL(url string) => (urlImageInfo string)
    """
    return url + '/imageInfo'

def Image90x90URL(url):
    url2 = url + '/imageMogr/auto-orient/thumbnail/!90x90r/gravity/center/crop/90x90'
    print url2
    return url2

def mkImageMogrifyParams(opts):
    keys = ["thumbnail", "gravity", "crop", "quality", "rotate", "format"]
    params_string = ""
    for key in keys:
        if opts.has_key(key) and opts[key] != None:
            params_string += "/" + str(key) + "/" + str(opts[key])
    if opts.has_key("auto_orient") and opts["auto_orient"] == True:
            params_string += "/auto-orient"
    return "imageMogr" + params_string

def ImageMogrifyPreviewURL(src_img_url, opts):
    return src_img_url + "?" + mkImageMogrifyParams(opts)
