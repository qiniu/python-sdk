import logging
import math
from collections import namedtuple
from concurrent import futures
from io import BytesIO
from itertools import chain
from os import path
from threading import Lock
from time import time

from qiniu.compat import is_seekable
from qiniu.auth import Auth
from qiniu.http import qn_http_client, ResponseInfo
from qiniu.utils import b, io_crc32, urlsafe_base64_encode

from qiniu.services.storage.uploaders.abc import ResumeUploaderBase
from qiniu.services.storage.uploaders.io_chunked import IOChunked


class ResumeUploaderV1(ResumeUploaderBase):
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
        context: _ResumeUploadV1Context

        Returns
        -------
        _ResumeUploadV1Context
        """
        if not isinstance(context, _ResumeUploadV1Context):
            raise TypeError('context must be an instance of _ResumeUploadV1Context')

        if not self.upload_progress_recorder or not any([file_name, key]):
            return context

        record = self.upload_progress_recorder.get_upload_record(
            file_name,
            key
        )

        if not record:
            return context

        record_up_hosts = record.get('up_hosts', [])
        record_part_size = record.get('part_size', None)
        record_modify_time = record.get('modify_time', 0)
        record_context = record.get('contexts', [])

        # compact with old sdk(<= v7.11.1)
        if not record_up_hosts or not record_part_size:
            return context

        # filter expired parts
        if record_modify_time != context.modify_time:
            record_context = []
        else:
            now = time()
            record_context = [
                ctx
                for ctx in record_context
                if (
                    ctx.get('expired_at', 0) > now and
                    ctx.get('part_no', None) and
                    ctx.get('ctx', None)
                )
            ]

        # assign to context
        return context._replace(
            up_hosts=record_up_hosts,
            part_size=record_part_size,
            parts=[
                _ResumeUploadV1Part(
                    part_no=p['part_no'],
                    ctx=p['ctx'],
                    expired_at=p['expired_at'],
                )
                for p in record_context
            ],
            resumed=True
        )

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
        context: _ResumeUploadV1Context

        """
        if not self.upload_progress_recorder or not any([file_name, key]):
            return

        record_data = {
            'up_hosts': context.up_hosts,
            'part_size': context.part_size,
            'modify_time': context.modify_time,
            'contexts': [
                {
                    'ctx': part.ctx,
                    'expired_at': part.expired_at,
                    'part_no': part.part_no
                }
                for part in context.parts
            ]
        }
        self.upload_progress_recorder.set_upload_record(
            file_name,
            key,
            data=record_data
        )

    def _try_delete_record(
        self,
        file_name,
        key,
        context,
        resp
    ):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: _ResumeUploadV1Context
        resp: ResponseInfo
        """
        if not self.upload_progress_recorder or not any([file_name, key]):
            return
        if resp and context and not any([
            resp.ok(),
            resp.status_code == 701 and context.resumed
        ]):
            return
        self.upload_progress_recorder.delete_upload_record(file_name, key)

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
        context: _ResumeUploadV1Context
        uploaded_size: int
        total_size: int

        """
        self._set_to_record(file_name, key, context)
        if callable(self.progress_handler):
            self.progress_handler(uploaded_size, total_size)

    def initial_parts(
        self,
        up_token,
        key,
        file_path=None,
        data=None,
        modify_time=None,
        data_size=None,
        file_name=None,
        **kwargs
    ):
        """
        Parameters
        ----------
        up_token
        key
        file_path
        data
        modify_time
        data_size
        file_name

        kwargs

        Returns
        -------
        context: _ResumeUploadV1Context
        resp: None

        """
        # -- check and initial arguments
        # must provide file_path or data
        if not file_path and not data:
            raise TypeError('Must provide one of file_path or data.')
        if file_path and data:
            raise TypeError('Must provide only one of file_path or data.')

        # data must has length
        if not file_path and not data_size:
            raise TypeError('Must provide size if use data.')

        if not modify_time:
            if file_path:
                modify_time = int(path.getmtime(file_path))
            else:
                modify_time = int(time())

        part_size = 4 * (1024 ** 2)

        # -- initial context
        context = _ResumeUploadV1Context(
            up_hosts=[],
            part_size=part_size,
            parts=[],
            modify_time=modify_time,
            resumed=False
        )

        # try to recover from record
        if not file_name and file_path:
            file_name = path.basename(file_path)
        context = self._recover_from_record(
            file_name,
            key,
            context
        )

        access_key, _, _ = Auth.up_token_decode(up_token)
        if not context.up_hosts:
            context.up_hosts.extend(self._get_up_hosts(access_key))

        return context, None

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
        context: _ResumeUploadV1Context
        data
        data_size: int

        kwargs
            key, file_name

        Returns
        -------
        part: _ResumeUploadV1Part
        resp: ResponseInfo

        """
        # initial arguments
        chunk_list = self.gen_chunk_list(
            size=data_size,
            chunk_size=context.part_size,
            uploaded_chunk_no_list=[
                p.part_no for p in context.parts
            ]
        )
        up_hosts = list(context.up_hosts)
        file_name = kwargs.get('file_name', None)
        key = kwargs.get('key', None)

        # initial upload state
        part, resp = None, None
        uploaded_size = context.part_size * len(context.parts)
        if math.ceil(data_size / context.part_size) in [p.part_no for p in context.parts]:
            # if last part uploaded, should correct the uploaded size
            uploaded_size += (data_size % context.part_size) - context.part_size
        lock = Lock()

        if not self.concurrent_executor:
            # upload sequentially
            for chunk in chunk_list:
                part, resp = self.__upload_part(
                    data=data,
                    chunk_info=chunk,
                    up_hosts=up_hosts,
                    up_token=up_token,
                    lock=lock
                )
                if not resp.ok():
                    return None, resp
                elif not part:
                    return resp.json(), resp
                context.parts.append(part)
                uploaded_size += chunk.chunk_size
                self._progress_handler(
                    file_name=file_name,
                    key=key,
                    context=context,
                    uploaded_size=uploaded_size,
                    total_size=data_size
                )
        else:
            # upload concurrently
            future_chunk_dict = {}
            for chunk in chunk_list:
                ftr = self.concurrent_executor.submit(
                    self.__upload_part,
                    data=data,
                    chunk_info=chunk,
                    up_hosts=up_hosts,
                    up_token=up_token,
                    lock=lock
                )
                future_chunk_dict[ftr] = chunk

            first_failed_resp = None
            for ftr in futures.as_completed(future_chunk_dict):
                if ftr.cancelled():
                    continue
                elif ftr.exception():
                    # only keep first failed future,
                    # continue instead return to wait running future done.
                    if first_failed_resp:
                        continue
                    first_failed_resp = ResponseInfo(None, ftr.exception())
                    for not_done in filter(lambda f: not f.done(), future_chunk_dict):
                        not_done.cancel()
                else:
                    part, resp = ftr.result()
                    if not part:
                        if not first_failed_resp:
                            first_failed_resp = resp
                            for not_done in filter(lambda f: not f.done(), future_chunk_dict):
                                not_done.cancel()
                    else:
                        context.parts.append(part)
                        uploaded_size += future_chunk_dict[ftr].chunk_size
                        self._progress_handler(
                            file_name=file_name,
                            key=key,
                            context=context,
                            uploaded_size=uploaded_size,
                            total_size=data_size
                        )
            if first_failed_resp:
                if first_failed_resp.ok():
                    # just compat with old sdk. it's ok when crc32 check failed
                    return first_failed_resp.json(), first_failed_resp
                return None, first_failed_resp

        return part, resp

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
        context: _ResumeUploadV1Context
        kwargs:
            key, file_name, params, metadata

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """
        key = kwargs.get('key', None)
        file_name = kwargs.get('file_name', None)
        params = kwargs.get('params', None)
        metadata = kwargs.get('metadata', None)
        mime_type = kwargs.get('mime_type', None)

        # sort contexts
        sorted_parts = sorted(context.parts, key=lambda part: part.part_no)
        body = ','.join((part.ctx for part in sorted_parts))

        ret, resp = None, None
        for up_host in context.up_hosts:
            url = self.__get_mkfile_url(
                up_host=up_host,
                data_size=data_size,
                mime_type=mime_type,
                key=key,
                file_name=file_name,
                params=params,
                metadata=metadata
            )
            ret, resp = qn_http_client.post(
                url=url,
                data=body,
                files=None,
                headers={
                    'Authorization': 'UpToken {}'.format(up_token)
                }
            )
            if resp.ok() or not resp.need_retry():
                break
        self._try_delete_record(
            file_name,
            key,
            context,
            resp
        )
        return ret, resp

    def upload(
        self,
        key,
        file_path=None,
        data=None,
        data_size=None,
        modify_time=None,

        part_size=None,
        mime_type=None,
        metadata=None,
        file_name=None,
        custom_vars=None,
        **kwargs
    ):
        """

        Parameters
        ----------
        key
        file_path
        data
        data_size
        modify_time

        part_size
        mime_type
        metadata
        file_name
        custom_vars

        kwargs:
            up_token
            bucket_name, expires, policy, strict_policy for generate `up_token`

        Returns
        -------
            ret: dict
            resp: ResponseInfo
        """
        # part_size
        if part_size:
            logging.warning('ResumeUploader not support part_size. It is fixed to 4MB.')

        # up_token
        up_token = kwargs.get('up_token', None)
        if not up_token:
            up_token = self.get_up_token(**kwargs)
        if not file_name and file_path:
            file_name = path.basename(file_path)

        # initial_parts
        context, resp = self.initial_parts(
            up_token,
            key,
            file_path=file_path,
            file_name=file_name,
            data=data,
            data_size=data_size,
            modify_time=modify_time,
        )

        # upload_parts
        try:
            if file_path:
                data_size = path.getsize(file_path)
                data = open(file_path, 'rb')
            elif isinstance(data, bytes):
                data_size = len(data)
                data = BytesIO(data)
            elif isinstance(data, str):
                data_size = len(data)
                data = BytesIO(b(data))
            ret, resp = self.upload_parts(
                up_token=up_token,
                context=context,
                data=data,
                data_size=data_size,

                key=key,
                file_name=file_name
            )
        finally:
            if file_path:
                data.close()

        if resp and not resp.ok():
            return ret, resp

        # complete_parts
        ret, resp = self.complete_parts(
            up_token=up_token,
            data_size=data_size,
            context=context,

            key=key,
            mime_type=mime_type,
            file_name=file_name,
            params=custom_vars,
            metadata=metadata
        )

        # retry if expired. the record file will be deleted by complete_parts
        if resp.status_code == 701 and context.resumed:
            return self.upload(
                key,
                file_path=file_path,
                data=data,
                data_size=data_size,
                modify_time=modify_time,

                mime_type=mime_type,
                metadata=metadata,
                file_name=file_name,
                custom_vars=custom_vars,
                **kwargs
            )

        return ret, resp

    def __upload_part(
        self,
        data,
        chunk_info,
        up_hosts,
        up_token,
        lock
    ):
        """
        Parameters
        ----------
        data: IOBase
        chunk_info: ChunkInfo
        up_hosts: list[str]
        up_token: str
        lock: Lock

        Returns
        -------
        part: _ResumeUploadV2Part
        resp: ResponseInfo
        """
        if not up_hosts:
            raise ValueError('Must provide one up host at least')

        chunked_data = IOChunked(
            base_io=data,
            chunk_offset=chunk_info.chunk_offset,
            chunk_size=chunk_info.chunk_size,
            lock=lock
        )
        chunk_crc32 = io_crc32(chunked_data)
        chunked_data.seek(0)
        part, resp = None, None
        for up_host in up_hosts:
            url = '/'.join([
                up_host,
                'mkblk', str(chunk_info.chunk_size)
            ])
            ret, resp = qn_http_client.post(
                url=url,
                data=chunked_data,
                files=None,
                headers={
                    'Authorization': 'UpToken {}'.format(up_token)
                }
            )
            if resp.ok() and ret:
                if ret.get('crc32', 0) != chunk_crc32:
                    return None, resp
                part = _ResumeUploadV1Part(
                    part_no=chunk_info.chunk_no,
                    ctx=ret.get('ctx', ''),
                    expired_at=ret.get('expired_at', 0),
                )
                return part, resp
            if (
                not is_seekable(chunked_data) or
                not resp.need_retry()
            ):
                return part, resp
            chunked_data.seek(0)
        return part, resp

    def __get_mkfile_url(
        self,
        up_host,
        data_size,
        mime_type=None,
        key=None,
        file_name=None,
        params=None,
        metadata=None
    ):
        """
        Parameters
        ----------
        up_host: str
        data_size: int
        mime_type: str
        key: str
        file_name: str
        params: dict
        metadata: dict

        Returns
        -------
        str
        """
        url_base = [up_host, 'mkfile', str(data_size)]
        url_params = []

        if mime_type:
            url_params.append(('mimeType', mime_type))

        if key:
            url_params.append(('key', key))

        if file_name:
            url_params.append(('fname', file_name))

        if params:
            url_params.extend(params.items())

        if metadata:
            url_params.extend(
                (k, v)
                for k, v in metadata.items()
                if k.startswith('x-qn-meta-')
            )

        url_params_iter = chain.from_iterable(
            (str(k), urlsafe_base64_encode(str(v)))
            for k, v in url_params
        )

        return '/'.join(
            chain(
                url_base,
                url_params_iter
            )
        )


# use dataclass instead namedtuple if min version of python update to 3.7
_ResumeUploadV1Part = namedtuple(
    'ResumeUploadV1Part',
    [
        'part_no',
        'ctx',
        'expired_at',
    ]
)

_ResumeUploadV1Context = namedtuple(
    'ResumeUploadV1Context',
    [
        'up_hosts',
        'part_size',
        'parts',
        'modify_time',  # the file last modify time
        'resumed'
    ]
)
