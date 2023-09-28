from io import BytesIO
from os import path
from time import time

from qiniu.compat import is_seekable
from qiniu.utils import b, io_crc32
from qiniu.auth import Auth
from qiniu.http import qn_http_client

from qiniu.services.storage.uploaders.abc import UploaderBase


class FormUploader(UploaderBase):
    def __init__(self, bucket_name, **kwargs):
        """
        Parameters
        ----------
        bucket_name: str
        kwargs
            auth, regions
        """
        super(FormUploader, self).__init__(bucket_name, **kwargs)

        self.progress_handler = kwargs.get(
            'progress_handler',
            None
        )

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
        key: str
        file_path: str
        data: IOBase
        data_size: int
        modify_time: int
        part_size: int
        mime_type: str
        metadata: dict
        file_name: str
        custom_vars: dict
        kwargs
            up_token, crc32_int
            bucket_name, key, expired, policy, strict_policy for get up_token

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """
        # check and initial arguments
        # up_token and up_hosts
        up_token = kwargs.get('up_token', None)
        if not up_token:
            up_token = self.get_up_token(**kwargs)
            up_hosts = self._get_up_hosts()
        else:
            access_key, _, _ = Auth.up_token_decode(up_token)
            up_hosts = self._get_up_hosts(access_key)

        # crc32 from outside
        crc32_int = kwargs.get('crc32_int', None)
        # try to get file_name
        if not file_name and file_path:
            file_name = path.basename(file_path)

        # must provide file_path or data
        if not file_path and not data:
            raise TypeError('Must provide one of file_path or data.')
        if file_path and data:
            raise TypeError('Must provide only one of file_path or data.')

        if not modify_time:
            if file_path:
                modify_time = int(path.getmtime(file_path))
            else:
                modify_time = int(time())

        # upload
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
            if not crc32_int:
                crc32_int = self.__get_crc32_int(data)
            fields = self.__get_form_fields(
                up_hosts=up_hosts,
                up_token=up_token,
                key=key,
                crc32_int=crc32_int,
                custom_vars=custom_vars,
                metadata=metadata
            )
            ret, resp = self.__upload_data(
                up_hosts=up_hosts,
                fields=fields,
                file_name=file_name,
                data=data,
                data_size=data_size,
                mime_type=mime_type
            )
        finally:
            if file_path:
                data.close()

        return ret, resp

    def __upload_data(
        self,
        up_hosts,
        fields,
        file_name,
        data,
        data_size=None,
        mime_type='application/octet-stream'
    ):
        """
        Parameters
        ----------
        up_hosts: list[str]
        fields: dict
        file_name: str
        data: IOBase
        data_size: int
        mime_type: str

        Returns
        -------
        ret: dict
        resp: ResponseInfo
        """
        if not file_name or not file_name.strip():
            file_name = 'file_name'

        ret, resp = None, None
        for up_host in up_hosts:
            ret, resp = qn_http_client.post(
                url=up_host,
                data=fields,
                files={
                    'file': (file_name, data, mime_type)
                }
            )
            if resp.ok() and ret:
                return ret, resp
            if (
                not is_seekable(data) or
                not resp.need_retry()
            ):
                return ret, resp
            data.seek(0)
        return ret, resp

    def __get_form_fields(
        self,
        up_token,
        **kwargs
    ):
        """
        Parameters
        ----------
        up_token: str
        kwargs
            key, crc32_int, custom_vars, metadata

        Returns
        -------
        dict
        """
        key = kwargs.get('key', None)
        crc32_int = kwargs.get('crc32_int', None)
        custom_vars = kwargs.get('custom_vars', None)
        metadata = kwargs.get('metadata', None)

        result = {
            'token': up_token,
        }

        if key is not None:
            result['key'] = key

        if crc32_int:
            result['crc32'] = crc32_int

        if custom_vars:
            result.update(
                {
                    k: str(v)
                    for k, v in custom_vars.items()
                    if k.startswith('x:')
                }
            )

        if metadata:
            result.update(
                {
                    k: str(v)
                    for k, v in metadata.items()
                    if k.startswith('x-qn-meta-')
                }
            )

        return result

    def __get_crc32_int(self, data):
        """
        Parameters
        ----------
        data: BytesIO

        Returns
        -------
        str
        """
        result = None
        if not is_seekable(data):
            return result
        result = io_crc32(data)
        data.seek(0)
        return result
