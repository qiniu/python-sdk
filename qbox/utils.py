import zlib


def crc32(body):
    return zlib.crc32(body) & 0xFFFFFFFF
