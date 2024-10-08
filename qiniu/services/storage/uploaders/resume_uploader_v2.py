import functools
import math
from collections import namedtuple
from concurrent import futures
from io import BytesIO
from os import path
from threading import Lock
from time import time

from qiniu.compat import is_seekable
from qiniu.auth import Auth
from qiniu.http import qn_http_client, ResponseInfo
from qiniu.http.endpoint import Endpoint
from qiniu.utils import b, io_md5, urlsafe_base64_encode
from qiniu.compat import json

from ._default_retrier import ProgressRecord, get_default_retrier
from .abc import ResumeUploaderBase
from .io_chunked import IOChunked


class ResumeUploaderV2(ResumeUploaderBase):
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
        context: _ResumeUploadV2Context

        Returns
        -------
        _ResumeUploadV2Context
        """
        if not isinstance(context, _ResumeUploadV2Context):
            raise TypeError('"context" must be an instance of _ResumeUploadV2Context')

        if (
            not self.upload_progress_recorder or
            not (file_name or key)
        ):
            return context

        record = self.upload_progress_recorder.get_upload_record(
            file_name,
            key
        )

        if not record:
            return context

        record_up_hosts = record.get('up_hosts', [])
        record_upload_id = record.get('upload_id', '')
        record_expired_at = record.get('expired_at', 0)
        record_part_size = record.get('part_size', None)
        record_modify_time = record.get('modify_time', 0)
        record_etags = record.get('etags', [])

        # compat with old sdk(<= v7.11.1)
        if not record_up_hosts or not record_part_size:
            return context

        if (
            not record_upload_id or
            record_modify_time != context.modify_time or
            record_expired_at < time()
        ):
            return context

        return context._replace(
            up_hosts=record_up_hosts,
            upload_id=record_upload_id,
            expired_at=record_expired_at,
            part_size=record_part_size,
            parts=[
                _ResumeUploadV2Part(
                    part_no=p['partNumber'],
                    etag=p['etag']
                )
                for p in record_etags
                if (
                    p.get('partNumber', None) and
                    p.get('etag', None)
                )
            ],
            resumed=True
        )

    def _set_to_record(self, file_name, key, context):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: _ResumeUploadV2Context

        """
        if not self.upload_progress_recorder or not any([file_name, key]):
            return

        record_data = {
            'up_hosts': context.up_hosts,
            'upload_id': context.upload_id,
            'expired_at': context.expired_at,
            'part_size': context.part_size,
            'modify_time': context.modify_time,
            'etags': [
                {
                    'etag': part.etag,
                    'partNumber': part.part_no
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
        context=None,
        resp=None
    ):
        """
        Parameters
        ----------
        file_name: str
        key: str
        context: _ResumeUploadV2Context
        resp: ResponseInfo
        """
        if not self.upload_progress_recorder or not any([file_name, key]):
            return
        if resp and not resp.ok():
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
        context: _ResumeUploadV2Context
        uploaded_size: int
        total_size: int
        """
        self._set_to_record(file_name, key, context)
        if not callable(self.progress_handler):
            return
        try:
            self.progress_handler(uploaded_size, total_size)
        except Exception as err:
            err.no_need_retry = True
            raise err

    def _initial_context(
        self,
        key,
        file_name,
        modify_time,
        part_size
    ):
        context = _ResumeUploadV2Context(
            up_hosts=[],
            upload_id='',
            expired_at=0,
            part_size=part_size,
            parts=[],
            modify_time=modify_time,
            resumed=False
        )

        # try to recover from record

        return self._recover_from_record(
            file_name,
            key,
            context
        )

    def initial_parts(
        self,
        up_token,
        key,
        file_path=None,
        data=None,
        data_size=None,
        modify_time=None,
        part_size=None,
        file_name=None,
        up_endpoint=None,
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
        file_name: str
        up_endpoint: Endpoint
        kwargs

        Returns
        -------
        ret: _ResumeUploadV2Context
        resp: ResponseInfo
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

        if not part_size:
            part_size = self.part_size

        # -- initial context
        if not file_name and file_path:
            file_name = path.basename(file_path)
        context = self._initial_context(
            key=key,
            file_name=file_name,
            modify_time=modify_time,
            part_size=part_size
        )

        if (
            context.up_hosts and
            context.upload_id and
            context.expired_at
        ):
            return context, None

        # -- get a new upload id
        if not context.up_hosts and up_endpoint:
            context.up_hosts.extend([up_endpoint.get_value(scheme=self.preferred_scheme)])

        if not context.up_hosts:
            access_key, _, _ = Auth.up_token_decode(up_token)
            context.up_hosts.extend(self._get_up_hosts(access_key))

        bucket_name = Auth.get_bucket_name(up_token)

        resp = None
        for up_host in context.up_hosts:
            url = self.__get_url_for_upload(
                up_host,
                bucket_name,
                key
            )
            ret, resp = qn_http_client.post(
                url=url,
                data='',
                files=None,
                headers={
                    'Authorization': 'UpToken {}'.format(up_token)
                }
            )
            if not resp.ok() and not resp.need_retry():
                break
            if resp.ok() and ret:
                context = context._replace(
                    upload_id=ret.get('uploadId', ''),
                    expired_at=ret.get('expireAt', 0)
                )
                break

        return context, resp

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
        data
        data_size: int
        context: _ResumeUploadV2Context
        kwargs
            key, file_name

        Returns
        -------
        part: _ResumeUploadV2Part
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
                    upload_id=context.upload_id,
                    key=key,
                    lock=lock
                )
                if not resp.ok():
                    return None, resp
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
                    upload_id=context.upload_id,
                    key=key,
                    lock=lock
                )
                future_chunk_dict[ftr] = chunk

            first_failed_resp = None
            for ftr in futures.as_completed(future_chunk_dict):
                if ftr.cancelled():
                    continue
                elif ftr.exception():
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
        context: _ResumeUploadV2Context
        kwargs
            key, file_name, params, metadata
        Returns
        -------
            ret: dict
            resp: ResponseInfo
        """
        key = kwargs.get('key', None)
        file_name = kwargs.get('file_name', None)
        mime_type = kwargs.get('mime_type', None)
        params = kwargs.get('params', None)
        metadata = kwargs.get('metadata', None)

        # sort contexts
        sorted_parts = sorted(context.parts, key=lambda part: part.part_no)

        bucket_name = Auth.get_bucket_name(up_token)

        ret, resp = None, None
        for up_host in context.up_hosts:
            url = self.__get_url_for_upload(
                up_host,
                bucket_name,
                key,
                upload_id=context.upload_id
            )
            data = {
                'parts': [
                    {
                        'etag': p.etag,
                        'partNumber': p.part_no
                    }
                    for p in sorted_parts
                ],
                'fname': file_name,
                'mimeType': mime_type,
                'customVars': params,
                'metadata': metadata
            }
            ret, resp = qn_http_client.post(
                url=url,
                data=json.dumps(data),
                files=None,
                headers={
                    'Content-Type': 'application/json',
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

    def __upload_with_retrier(
        self,
        access_key,
        bucket_name,
        **upload_opts
    ):
        file_name = upload_opts.get('file_name', None)
        key = upload_opts.get('key', None)
        modify_time = upload_opts.get('modify_time', None)
        part_size = upload_opts.get('part_size', self.part_size)

        context = self._initial_context(
            key=key,
            file_name=file_name,
            modify_time=modify_time,
            part_size=part_size
        )
        preferred_endpoints = None
        if context.up_hosts:
            preferred_endpoints = [
                Endpoint.from_host(h)
                for h in context.up_hosts
            ]

        progress_record = None
        if all(
            [
                self.upload_progress_recorder,
                file_name,
                key
            ]
        ):
            progress_record = ProgressRecord(
                upload_api_version='v1',
                exists=functools.partial(
                    self.upload_progress_recorder.has_upload_record,
                    file_name=file_name,
                    key=key
                ),
                delete=functools.partial(
                    self.upload_progress_recorder.delete_upload_record,
                    file_name=file_name,
                    key=key
                )
            )

        retrier = get_default_retrier(
            regions_provider=self._get_regions_provider(
                access_key=access_key,
                bucket_name=bucket_name
            ),
            preferred_endpoints_provider=preferred_endpoints,
            progress_record=progress_record,
            accelerate_uploading=self.accelerate_uploading
        )

        data = upload_opts.get('data')
        attempt = None
        for attempt in retrier:
            with attempt:
                upload_opts['up_endpoint'] = attempt.context.get('endpoint')
                attempt.result = self.__upload(
                    **upload_opts
                )
                ret, resp = attempt.result
                if resp.ok() and ret:
                    return attempt.result
                if (
                    not is_seekable(data) or
                    not resp.need_retry()
                ):
                    return attempt.result
                data.seek(0)

        if attempt is None:
            raise RuntimeError('Retrier is not working. attempt is None')

        return attempt.result

    def __upload(
        self,
        up_token,
        key,
        file_path,
        file_name,
        data,
        data_size,
        part_size,
        modify_time,
        mime_type,
        custom_vars,
        metadata,
        up_endpoint
    ):
        # initial_parts
        context, resp = self.initial_parts(
            up_token,
            key,
            file_path=file_path,
            file_name=file_name,
            data=data,
            data_size=data_size,
            modify_time=modify_time,
            part_size=part_size,
            up_endpoint=up_endpoint
        )

        if (
            not context.up_hosts or
            not context.upload_id or
            not context.expired_at
        ):
            return None, resp

        # upload parts
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
                data=data,
                data_size=data_size,
                context=context,

                key=key,
                file_name=file_name
            )
        finally:
            if file_path:
                data.close()

        if resp and not resp.ok():
            return ret, resp

        # complete parts
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

        return ret, resp

    def upload(
        self,
        key,
        file_path=None,
        data=None,
        data_size=None,

        part_size=None,
        modify_time=None,
        mime_type=None,
        metadata=None,
        file_name=None,
        custom_vars=None,
        **kwargs
    ):
        """
        Parameters
        ----------
        key: str
        file_path: str
        data: IOBase
        data_size: int
        part_size: int
        modify_time: int
        mime_type: str
        metadata: dict
        file_name: str
        custom_vars: dict
        kwargs
            up_token: str
            bucket_name: str,
            expired: int,
            policy: dict,
            strict_policy: bool

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """
        # up_token
        up_token = kwargs.get('up_token', None)
        if not up_token:
            kwargs.setdefault('up_token', self.get_up_token(**kwargs))
            access_key = self.auth.get_access_key()
        else:
            access_key, _, _ = Auth.up_token_decode(up_token)

        # bucket_name
        kwargs['bucket_name'] = Auth.get_bucket_name(up_token)

        # file_name
        if not file_name and file_path:
            file_name = path.basename(file_path)

        # upload
        return self.__upload_with_retrier(
            access_key=access_key,
            key=key,
            file_path=file_path,
            file_name=file_name,
            data=data,
            data_size=data_size,
            part_size=part_size,
            modify_time=modify_time,
            mime_type=mime_type,
            custom_vars=custom_vars,
            metadata=metadata,
            **kwargs
        )

    def __get_url_for_upload(
        self,
        up_host,
        bucket_name,
        key,
        upload_id=None,
        part_no=None,
    ):
        """
        Parameters
        ----------
        up_host: str
        bucket_name: str
        key: str
        upload_id: str
        part_no: int

        Returns
        -------
        str
        """
        if not bucket_name:
            bucket_name = self.bucket_name

        object_entry = '~'
        if key:
            object_entry = urlsafe_base64_encode(key)

        url_segs = [
            up_host,
            'buckets', bucket_name,
            'objects', object_entry,
            'uploads',
        ]

        if upload_id:
            url_segs.append(upload_id)

        if part_no:
            url_segs.append(str(part_no))

        return '/'.join(url_segs)

    def __upload_part(
        # resort arguments
        self,
        data,
        chunk_info,
        up_hosts,
        up_token,
        upload_id,
        key,
        lock
    ):
        """
        Parameters
        ----------
        data: IOBase
        chunk_info: ChunkInfo
        up_hosts: list[str]
        up_token: str
        upload_id: str
        key: str
        lock: Lock

        Returns
        -------
        part: _ResumeUploadV2Part
        resp: ResponseInfo
        """
        if not up_hosts:
            raise ValueError('Must provide on up host at least')

        bucket_name = Auth.get_bucket_name(up_token)
        if not bucket_name:
            bucket_name = self.bucket_name

        chunked_data = IOChunked(
            base_io=data,
            chunk_offset=chunk_info.chunk_offset,
            chunk_size=chunk_info.chunk_size,
            lock=lock
        )
        chunk_md5 = io_md5(chunked_data)
        chunked_data.seek(0)
        part, resp = None, None
        for up_host in up_hosts:
            url = self.__get_url_for_upload(
                up_host,
                bucket_name,
                key,
                upload_id=upload_id,
                part_no=chunk_info.chunk_no
            )
            ret, resp = qn_http_client.put(
                url=url,
                data=chunked_data,
                files=None,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-MD5': chunk_md5,
                    'Authorization': 'UpToken {}'.format(up_token)
                }
            )
            if resp.ok() and ret:
                part = _ResumeUploadV2Part(
                    part_no=chunk_info.chunk_no,
                    etag=ret.get('etag', '')
                )
                return part, resp
            if (
                not is_seekable(chunked_data) or
                not resp.need_retry()
            ):
                return part, resp
            chunked_data.seek(0)
        return part, resp


# use dataclass instead namedtuple if min version of python update to 3.7
_ResumeUploadV2Part = namedtuple(
    'ResumeUploadV2Part',
    [
        'part_no',
        'etag'
    ]
)

_ResumeUploadV2Context = namedtuple(
    'ResumeUploadV2Context',
    [
        'up_hosts',
        'upload_id',
        'expired_at',
        'part_size',
        'parts',
        'modify_time',
        'resumed'
    ]
)
