# -*- coding: utf-8 -*-

ACCESS_KEY = ""
SECRET_KEY = ""

RS_HOST = "rs.qbox.me"
RSF_HOST = "rsf.qbox.me"
UP_HOST = "up.qiniu.com"
UP_HOST2 = "upload.qbox.me"

from . import __version__
import platform

sys_info = "%s/%s" % (platform.system(), platform.machine())
py_ver = platform.python_version()

USER_AGENT = "QiniuPython/%s (%s) Python/%s" % (__version__, sys_info, py_ver)
