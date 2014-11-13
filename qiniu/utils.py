# -*- coding: utf-8 -*-

from hashlib import sha1
from base64 import urlsafe_b64encode, urlsafe_b64decode

from .config import _BLOCK_SIZE

from .compat import b, s

try:
    import zlib
    binascii = zlib
except ImportError:
    zlib = None
    import binascii


def urlsafe_base64_encode(data):
    ret = urlsafe_b64encode(b(data))
    return s(ret)


def urlsafe_base64_decode(data):
    ret = urlsafe_b64decode(s(data))
    return ret


def file_crc32(filePath):
    crc = 0
    with open(filePath, 'rb') as f:
        for block in _file_iter(f, _BLOCK_SIZE):
            crc = binascii.crc32(block, crc) & 0xFFFFFFFF
    return crc


def crc32(data):
    return binascii.crc32(b(data)) & 0xffffffff


def _file_iter(input_stream, size):
    d = input_stream.read(size)
    while d:
        yield d
        d = input_stream.read(size)


def _sha1(data):
    h = sha1()
    h.update(data)
    return h.digest()


def _etag(input_stream):
    array = [_sha1(block) for block in _file_iter(input_stream, _BLOCK_SIZE)]
    if len(array) == 1:
        data = array[0]
        prefix = b('\x16')
    else:
        s = b('').join(array)
        data = _sha1(s)
        prefix = b('\x96')
    return urlsafe_base64_encode(prefix + data)


def etag(filePath):
    with open(filePath, 'rb') as f:
        return _etag(f)


def entry(bucket, key):
    return urlsafe_base64_encode('{0}:{1}'.format(bucket, key))
