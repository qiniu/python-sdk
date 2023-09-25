import abc
from concurrent import futures

from qiniu.services.storage.uploaders.io_chunked import ChunkInfo
from qiniu.services.storage.uploaders.abc import UploaderBase


class ResumeUploaderBase(UploaderBase):
    """
    Attributes
    ----------
    part_size: int, optional
    progress_handler: function, optional
    upload_progress_recorder: UploadProgressRecorder, optional
    concurrent_executor: futures.Executor, optional
    """
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        bucket_name,
        **kwargs
    ):
        """
        Parameters
        ----------
        bucket_name
        part_size: int
        progress_handler: function
        upload_progress_recorder: UploadProgressRecorder
        max_concurrent_workers: int
        concurrent_executor: futures.Executor
        kwargs
        """
        super().__init__(bucket_name, **kwargs)

        self.part_size = kwargs.get('part_size', 4 * (1024 ** 2))

        self.progress_handler = kwargs.get(
            'progress_handler',
            None
        )

        self.upload_progress_recorder = kwargs.get(
            'upload_progress_recorder',
            None
        )

        max_workers = kwargs.get('max_concurrent_workers', 3)
        self.concurrent_executor = kwargs.get(
            'concurrent_executor',
            futures.ThreadPoolExecutor(max_workers=max_workers)
        )

    def gen_chunk_list(self, size, chunk_size=None, uploaded_chunk_no_list=None):
        """
        Parameters
        ----------
        size: int
        chunk_size: int
        uploaded_chunk_no_list: list[int]

        Yields
        -------
            ChunkInfo
        """
        if not chunk_size:
            chunk_size = self.part_size
        if not uploaded_chunk_no_list:
            uploaded_chunk_no_list = []

        for i, chunk_offset in enumerate(range(0, size, chunk_size)):
            chunk_no = i + 1
            if chunk_no in uploaded_chunk_no_list:
                continue
            yield ChunkInfo(
                chunk_no=chunk_no,
                chunk_offset=chunk_offset,
                chunk_size=min(
                    chunk_size,
                    size - chunk_offset
                )
            )

    @abc.abstractmethod
    def _recover_from_record(
        self,
        file_name,
        key,
        context
    ):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: any

        Returns
        -------
        any
        """

    @abc.abstractmethod
    def _set_to_record(
        self,
        file_name,
        key,
        context
    ):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: any
        """

    @abc.abstractmethod
    def _progress_handler(
        self,
        file_name,
        key,
        context,
        uploaded_size,
        total_size
    ):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: any
        uploaded_size: int
        total_size: int
        """

    @abc.abstractmethod
    def initial_parts(
        self,
        up_token,
        key,
        file_path,
        data,
        data_size,
        modify_time,
        part_size,
        **kwargs
    ):
        """
        Parameters
        ----------
        up_token: str
        key: str
        file_path: str
        data: IOBase
        data_size: int
        modify_time: int
        part_size: int
        kwargs: dict

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """

    @abc.abstractmethod
    def upload_parts(
        self,
        up_token,
        data,
        data_size,
        context,
        **kwargs
    ):
        """
        Parameters
        ----------
        up_token: str
        data: IOBase
        data_size: int
        context: any
        kwargs: dict

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """

    @abc.abstractmethod
    def complete_parts(
        self,
        up_token,
        data_size,
        context,
        **kwargs
    ):
        """
        Parameters
        ----------
        up_token: str
        data_size: int
        context: any
        kwargs: dictr

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """
