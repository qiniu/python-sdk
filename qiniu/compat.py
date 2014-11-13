# -*- coding: utf-8 -*-

"""
pythoncompat
"""

import sys

try:
    import simplejson as json
except (ImportError, SyntaxError):
    # simplejson does not support Python 3.2, it thows a SyntaxError
    # because of u'...' Unicode literals.
    import json  # noqa


# -------
# Pythons
# -------

_ver = sys.version_info

#: Python 2.x?
is_py2 = (_ver[0] == 2)

#: Python 3.x?
is_py3 = (_ver[0] == 3)


# ---------
# Specifics
# ---------

if is_py2:
    from urlparse import urlparse  # noqa
    import StringIO
    StringIO = BytesIO = StringIO.StringIO

    builtin_str = str
    bytes = str
    str = unicode  # noqa
    basestring = basestring  # noqa
    numeric_types = (int, long, float)  # noqa

    def b(s):
        return s

    def s(b):
        return b

    def u(s):
        return unicode(s, 'unicode_escape')  # noqa

elif is_py3:
    from urllib.parse import urlparse  # noqa
    import io
    StringIO = io.StringIO
    BytesIO = io.BytesIO

    builtin_str = str
    str = str
    bytes = bytes
    basestring = (str, bytes)
    numeric_types = (int, float)

    def b(s):
        if isinstance(s, str):
            return s.encode('utf-8')
        return s

    def s(b):
        if isinstance(b, bytes):
            b = b.decode('utf-8')
        return b

    def u(s):
        return s
