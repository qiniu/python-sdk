# -*- coding: utf-8 -*-

ACCESS_KEY = ""
SECRET_KEY = ""

RS_HOST = "rs.qbox.me"
RSF_HOST = "rsf.qbox.me"
UP_HOST = "up.qiniu.com"

from . import __version__
import platform

sys_info = "%s/%s" % (platform.system(), platform.machine())
py_ver = platform.python_version()

USER_AGENT = "QiniuPython/%s (%s) Python/%s" % (__version__, sys_info, py_ver)

import sys
# mark current python version
PY2 = sys.version_info < (3, 0)
