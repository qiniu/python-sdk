# -*- coding: utf-8 -*-

"""
pythoncompat
"""

import os
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
    from urllib import urlencode  # noqa
    from urlparse import urlparse  # noqa
    import StringIO
    import enum34
    StringIO = BytesIO = StringIO.StringIO
    Enum = enum34.Enum

    builtin_str = str
    bytes = str
    str = unicode  # noqa
    basestring = basestring  # noqa
    numeric_types = (int, long, float)  # noqa

    def b(data):
        return bytes(data)

    def s(data):
        return bytes(data)

    def u(data):
        return unicode(data, 'unicode_escape')  # noqa

    def is_seekable(data):
        try:
            data.seek(0, os.SEEK_CUR)
            return True
        except (AttributeError, IOError):
            return False

elif is_py3:
    from urllib.parse import urlparse, urlencode  # noqa
    import io
    import enum
    StringIO = io.StringIO
    BytesIO = io.BytesIO
    Enum = enum.Enum

    builtin_str = str
    str = str
    bytes = bytes
    basestring = (str, bytes)
    numeric_types = (int, float)

    def b(data):
        if isinstance(data, str):
            return data.encode('utf-8')
        return data

    def s(data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data

    def u(data):
        return data

    def is_seekable(data):
        return data.seekable()
