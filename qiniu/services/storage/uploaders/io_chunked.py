import io
from collections import namedtuple

from qiniu.compat import is_seekable


ChunkInfo = namedtuple(
    'ChunkInfo',
    [
        'chunk_no',
        'chunk_offset',
        'chunk_size'
    ]
)


class IOChunked(io.IOBase):
    def __init__(
        self,
        base_io,
        chunk_offset,
        chunk_size,
        lock,
        buffer_size=4 * (1024 ** 2)  # 4MB just for demo
    ):
        if not is_seekable(base_io):
            raise TypeError('"base_io" must be seekable')
        self.__base_io = base_io
        self.__chunk_start = chunk_offset
        self.__chunk_size = chunk_size
        self.__chunk_end = chunk_offset + chunk_size
        self.__lock = lock
        self.__chunk_pos = 0

        self.buffer_size = min(buffer_size, chunk_size)

    def readable(self):
        return self.__base_io.readable()

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if not self.seekable():
            raise io.UnsupportedOperation('does not support seek')
        if whence == 0:
            if offset < 0:
                raise ValueError('offset should be zero or positive if whence is 0')
            self.__chunk_pos = offset
        elif whence == 1:
            self.__chunk_pos += offset
        elif whence == 2:
            if offset > 0:
                raise ValueError('offset should be zero or negative if whence is 2')
            self.__chunk_pos = self.__chunk_size + offset
        else:
            raise ValueError('whence should be 0, 1 or 2')
        self.__chunk_pos = max(
            0,
            min(self.__chunk_size, self.__chunk_pos)
        )

    def tell(self):
        return self.__chunk_pos

    def read(self, size):
        if self.__curr_base_pos >= self.__chunk_end:
            return b''
        read_size = max(self.buffer_size, size)
        read_size = min(self.__chunk_end - self.__chunk_pos, read_size)

        # -- ignore size argument --
        with self.__lock:
            self.__base_io.seek(self.__curr_base_pos)
            data = self.__base_io.read(read_size)

        self.__chunk_pos += len(data)
        return data

    def __len__(self):
        return self.__chunk_size

    @property
    def __curr_base_pos(self):
        return self.__chunk_start + self.__chunk_pos
