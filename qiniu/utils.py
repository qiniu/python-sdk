# -*- coding: utf-8 -*-
from hashlib import sha1, new as hashlib_new
from base64 import urlsafe_b64encode, urlsafe_b64decode
from datetime import datetime, tzinfo, timedelta

from .compat import b, s

try:
    import zlib

    binascii = zlib
except ImportError:
    zlib = None
    import binascii

_BLOCK_SIZE = 1024 * 1024 * 4


def urlsafe_base64_encode(data):
    """urlsafe的base64编码:

    对提供的数据进行urlsafe的base64编码。规格参考：
    https://developer.qiniu.com/kodo/manual/1231/appendix#1

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
    with open(filePath, 'rb') as f:
        for block in _file_iter(f, _BLOCK_SIZE):
            crc = binascii.crc32(block, crc) & 0xFFFFFFFF
    return crc


def io_crc32(io_data):
    result = 0
    for d in io_data:
        result = binascii.crc32(d, result) & 0xFFFFFFFF
    return result


def io_md5(io_data):
    h = hashlib_new('md5')
    for d in io_data:
        h.update(d)
    return h.hexdigest()


def crc32(data):
    """计算输入流的crc32检验码:

    Args:
        data: 待计算校验码的字符流

    Returns:
        输入流的crc32校验码。
    """
    return binascii.crc32(b(data)) & 0xffffffff


def _file_iter(input_stream, size, offset=0):
    """读取输入流:

    Args:
        input_stream: 待读取文件的二进制流
        size:         二进制流的大小

    Raises:
        IOError: 文件流读取失败
    """
    input_stream.seek(offset)
    d = input_stream.read(size)
    while d:
        yield d
        d = input_stream.read(size)
    input_stream.seek(0)


def _sha1(data):
    """单块计算hash:

    Args:
        data: 待计算hash的数据

    Returns:
        输入数据计算的hash值
    """
    h = sha1()
    h.update(data)
    return h.digest()


def etag_stream(input_stream):
    """
    计算输入流的etag

    .. deprecated::
        在 v2 分片上传使用 4MB 以外分片大小时无法正常工作

    Parameters
    ----------
    input_stream: io.IOBase
        支持随机访问的文件型对象

    Returns
    -------
    str

    """
    array = [_sha1(block) for block in _file_iter(input_stream, _BLOCK_SIZE)]
    if len(array) == 0:
        array = [_sha1(b'')]
    if len(array) == 1:
        data = array[0]
        prefix = b'\x16'
    else:
        sha1_str = b('').join(array)
        data = _sha1(sha1_str)
        prefix = b'\x96'
    return urlsafe_base64_encode(prefix + data)


def etag(filePath):
    """
    计算文件的etag:

    .. deprecated::
        在 v2 分片上传使用 4MB 以外分片大小时无法正常工作


    Parameters
    ----------
    filePath: str
        待计算 etag 的文件路径

    Returns
    -------
    str
        输入文件的etag值
    """
    with open(filePath, 'rb') as f:
        return etag_stream(f)


def entry(bucket, key):
    """计算七牛API中的数据格式:

    entry规格参考 https://developer.qiniu.com/kodo/api/1276/data-format

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


def decode_entry(e):
    return (s(urlsafe_base64_decode(e)).split(':') + [None] * 2)[:2]


def rfc_from_timestamp(timestamp):
    """将时间戳转换为HTTP RFC格式

    Args:
        timestamp: 整型Unix时间戳（单位秒）
    """
    last_modified_date = datetime.utcfromtimestamp(timestamp)
    last_modified_str = last_modified_date.strftime(
        '%a, %d %b %Y %H:%M:%S GMT')
    return last_modified_str


def _valid_header_key_char(ch):
    is_token_table = [
        "!", "#", "$", "%", "&", "\\", "*", "+", "-", ".",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
        "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
        "U", "W", "V", "X", "Y", "Z",
        "^", "_", "`",
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
        "k", "l", "m", "n", "o", "p", "q", "r", "s", "t",
        "u", "v", "w", "x", "y", "z",
        "|", "~"]
    return 0 <= ord(ch) < 128 and ch in is_token_table


def canonical_mime_header_key(field_name):
    for ch in field_name:
        if not _valid_header_key_char(ch):
            return field_name
    result = ""
    upper = True
    for ch in field_name:
        if upper and "a" <= ch <= "z":
            result += ch.upper()
        elif not upper and "A" <= ch <= "Z":
            result += ch.lower()
        else:
            result += ch
        upper = ch == "-"
    return result


class _UTC_TZINFO(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)


def dt2ts(dt):
    """
    converte datetime to timestamp

    Parameters
    ----------
    dt: datetime.datetime
    """
    if not dt.tzinfo:
        st = (dt - datetime(1970, 1, 1)).total_seconds()
    else:
        st = (dt - datetime(1970, 1, 1, tzinfo=_UTC_TZINFO())).total_seconds()

    return int(st)
