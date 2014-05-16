# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

try:
    from io import StringIO
except:
    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO

import json

from . import conf
from . import httplib_chunk as httplib


class Client(object):
    _conn = None
    _header = None

    def __init__(self, host):
        self._conn = httplib.HTTPConnection(host)
        self._header = {}

    def round_tripper(self, method, path, body):
        self._conn.request(method, path, body, self._header)
        resp = self._conn.getresponse()
        return resp

    def call(self, path):
        return self.call_with(path, None)

    def call_with(self, path, body, content_type=None, content_length=None):
        ret = None

        self.set_header("User-Agent", conf.USER_AGENT)
        if content_type is not None:
            self.set_header("Content-Type", content_type)

        if content_length is not None:
            self.set_header("Content-Length", content_length)

        resp = self.round_tripper("POST", path, body)
        try:
            ret = resp.read()
            ret = json.loads(ret.decode())
        except IOError as e:
            return None, e
        except ValueError:
            pass

        if resp.status / 100 != 2:
            err_msg = ret if "error" not in ret else ret["error"]
            reqid = resp.getheader("X-Reqid", None)
            # detail = resp.getheader("x-log", None)
            if reqid is not None:
                err_msg += ", reqid:%s" % reqid

            return None, err_msg

        return ret, None

    def call_with_multipart(self, path, fields=None, files=None):
        """
         *  fields => {key}
         *  files => [{filename, data, content_type}]
        """
        content_type, mr = self.encode_multipart_formdata(fields, files)
        return self.call_with(path, mr, content_type, mr.length())

    def call_with_form(self, path, ops):
        """
         * ops => {"key": value/list()}
        """

        body = []
        for i in ops:
            if isinstance(ops[i], (list, tuple)):
                data = ('&%s=' % i).join(ops[i])
            else:
                data = ops[i]

            body.append('%s=%s' % (i, data))
        body = '&'.join(body)

        content_type = "application/x-www-form-urlencoded"
        return self.call_with(path, body, content_type, len(body))

    def set_header(self, field, value):
        self._header[field] = value

    def set_headers(self, headers):
        self._header.update(headers)

    def encode_multipart_formdata(self, fields, files):
        """
         *  fields => {key}
         *  files => [{filename, data, content_type}]
         *  return content_type, content_length, body
        """
        if files is None:
            files = []
        if fields is None:
            fields = {}

        readers = []
        BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
        CRLF = '\r\n'
        L1 = []
        for key in fields:
            L1.append('--' + BOUNDARY)
            L1.append('Content-Disposition: form-data; name="%s"' % key)
            L1.append('')
            L1.append(fields[key])
        b1 = CRLF.join(L1)
        readers.append(b1)

        for file_info in files:
            L = []
            L.append('')
            L.append('--' + BOUNDARY)
            disposition = "Content-Disposition: form-data;"
            filename = _qiniu_escape(file_info.get('filename'))
            L.append('%s name="file"; filename="%s"' % (disposition, filename))
            L.append('Content-Type: %s' %
                     file_info.get('mime_type', 'application/octet-stream'))
            L.append('')
            L.append('')
            b2 = CRLF.join(L)
            readers.append(b2)

            data = file_info.get('data')
            readers.append(data)

        L3 = ['', '--' + BOUNDARY + '--', '']
        b3 = CRLF.join(L3)
        readers.append(b3)

        content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
        return content_type, MultiReader(readers)


def _qiniu_escape(s):
    edits = [('\\', '\\\\'), ('\"', '\\\"')]
    for (search, replace) in edits:
        s = s.replace(search, replace)
    return s


class MultiReader(object):

    """ class MultiReader([readers...])

    MultiReader returns a read()able object that's the logical concatenation of
    the provided input readers.  They're read sequentially.
    """

    def __init__(self, readers):
        self.readers = []
        self.content_length = 0
        self.valid_content_length = True
        for r in readers:
            if hasattr(r, 'read'):
                if self.valid_content_length:
                    length = self._get_content_length(r)
                    if length is not None:
                        self.content_length += length
                    else:
                        self.valid_content_length = False
            else:
                buf = r
                r = StringIO(buf)
                buf = encode_unicode(buf)
                self.content_length += len(buf)
            self.readers.append(r)

    # don't name it __len__, because the length of MultiReader is not alway
    # valid.
    def length(self):
        return self.content_length if self.valid_content_length else None

    def _get_content_length(self, reader):
        data_len = None
        if hasattr(reader, 'seek') and hasattr(reader, 'tell'):
            try:
                reader.seek(0, 2)
                data_len = reader.tell()
                reader.seek(0, 0)
            except OSError:
                # Don't send a length if this failed
                data_len = None
        return data_len

    def read(self, n=-1):
        if n is None or n == -1:
            data = b''.join([encode_unicode(r.read()) for r in self.readers])
        else:
            L = []
            while len(self.readers) > 0 and n > 0:
                b = self.readers[0].read(n)
                if len(b) == 0:
                    self.readers = self.readers[1:]
                else:
                    if isinstance(b, str):
                        b = b.encode()
                    L.append(encode_unicode(b))
                    n -= len(b)
            data = b''.join(L)
        return data


def encode_unicode(u):
    if conf.PY2:
        if not isinstance(u, unicode):
            u = u.decode('utf8')
    else:
        if isinstance(u, str):
            u = u.encode('utf8')
    return u
