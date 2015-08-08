# -*- coding: utf-8 -*-

import os
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
    """urlsafe的base64编码:

    对提供的数据进行urlsafe的base64编码。规格参考：
    http://developer.qiniu.com/docs/v6/api/overview/appendix.html#urlsafe-base64

    Args:
        data: 待编码的数据，一般为字符串

    Returns:
        编码后的字符串
    """
    ret = urlsafe_b64encode(b(data))
    return s(ret)


def urlsafe_base64_decode(data):
    """urlsafe的base64解码:

    对提供的urlsafe的base64编码的数据进行解码

    Args:
        data: 待解码的数据，一般为字符串

    Returns:
        解码后的字符串。
    """
    ret = urlsafe_b64decode(s(data))
    return ret


def file_crc32(filePath):
    """计算文件的crc32检验码:

    Args:
        filePath: 待计算校验码的文件路径

    Returns:
        文件内容的crc32校验码。
    """
    crc = 0
    for block in _file_block_generator(filePath):
        crc = binascii.crc32(block, crc) & 0xFFFFFFFF
    return crc


def file_block_crc32(block_generator):
    """计算文件块的crc32检验码:

    Args:
        block_generator: 待计算校验码的文件块

    Returns:
        文件块的crc32校验码。
    """
    crc = 0
    for block in block_generator:
        crc = binascii.crc32(block, crc) & 0xFFFFFFFF
    return crc


def crc32(data):
    """计算输入流的crc32检验码:

    Args:
        data: 待计算校验码的字符流

    Returns:
        输入流的crc32校验码。
    """
    return binascii.crc32(b(data)) & 0xffffffff


class _file_block_generator(object):
    """用于读取文件片段的对象

    Args:
        filePath:   待读取的文件路径和名称
        offset:     文件片段开始的位移
        length:     文件片段的长度

    使用例子:
        for data in _file_block_generator("foo.bin", 1024*1024, 512*1024):
            print data
    """
    def __init__(self, filePath, offset=0, length=None):
        self.filePath = filePath
        self.offset = offset
        if length:
            self.length = length
        else:
            self.length = os.stat(filePath).st_size

    def __iter__(self):
        self.f = open(self.filePath,'rb')
        self.f.seek(self.offset)
        self.done = False
        self.rest = self.length
        return self

    # Python 3 Compatibility
    def __next__(self):
        return self.next()

    def next(self):
        #Choose 8192 because httplib has hard-coded read size of 8192
        if self.done:
            raise StopIteration
        if self.rest <= 8192:
            data = self.f.read(self.rest)
            self.done = True
            self.rest = 0
            self.f.close()
            return data
        else:
            self.rest -= 8192
            return self.f.read(8192)


def _file_iter(filePath, size, offset=0):
    """分片段读取文件:

    Args:
        filePath:   待读取文件
        size:       每个片段的大小
        offset:     第一个片段开始的位移

    Raises:
        IOError: 文件读取失败
    """
    file_size = os.stat(filePath).st_size
    while offset < file_size - size:
        yield _file_block_generator(filePath, offset, size)
        offset += size
    if offset < file_size:
        yield _file_block_generator(filePath, offset, file_size - offset)


def _sha1(block_generator):
    """单块计算hash:

    Args:
        block_generator: 待计算hash的数据片段

    Returns:
        输入数据计算的hash值
    """
    h = sha1()
    for data in block_generator:
        h.update(data)
    return h.digest()


def etag(filePath):
    """计算文件的etag:
    
    etag规格参考 http://developer.qiniu.com/docs/v6/api/overview/appendix.html#qiniu-etag

    Args:
        filePath: 待计算etag的文件路径

    Returns:
        输入文件的etag值
    """
    array = [_sha1(block) for block in _file_iter(filePath, _BLOCK_SIZE)]
    if len(array) == 1:
        data = array[0]
        prefix = b('\x16')
    else:
        sha1_str = b('').join(array)
        data = _sha1(sha1_str)
        prefix = b('\x96')
    return urlsafe_base64_encode(prefix + data)

def entry(bucket, key):
    """计算七牛API中的数据格式:

    entry规格参考 http://developer.qiniu.com/docs/v6/api/reference/data-formats.html

    Args:
        bucket: 待操作的空间名
        key:    待操作的文件名

    Returns:
        符合七牛API规格的数据格式
    """
    if key is None:
        return urlsafe_base64_encode('{0}'.format(bucket))
    else:
        return urlsafe_base64_encode('{0}:{1}'.format(bucket, key))
