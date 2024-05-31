# -*- coding: utf-8 -*-
import os

from qiniu.config import _BLOCK_SIZE, get_default

from qiniu.auth import Auth
from qiniu.utils import crc32, file_crc32, rfc_from_timestamp

from qiniu.services.storage.uploaders import FormUploader, ResumeUploaderV1, ResumeUploaderV2
from qiniu.services.storage.upload_progress_recorder import UploadProgressRecorder

# for compact to old sdk
from qiniu.services.storage.legacy import _Resume # noqa


def put_data(
    up_token, key, data, params=None, mime_type='application/octet-stream', check_crc=False, progress_handler=None,
    fname=None, hostscache_dir=None, metadata=None
):
    """上传二进制流到七牛

    Args:
        up_token:         上传凭证
        key:              上传文件名
        data:             上传二进制流
        params:           自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
        mime_type:        上传数据的mimeType
        check_crc:        是否校验crc32
        progress_handler: 上传进度
        hostscache_dir:   host请求 缓存文件保存位置
        metadata:         元数据

    Returns:
        一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
        一个ResponseInfo对象
    """
    final_data = b''
    if hasattr(data, 'read'):
        while True:
            tmp_data = data.read(_BLOCK_SIZE)
            if len(tmp_data) == 0:
                break
            else:
                final_data += tmp_data
    else:
        final_data = data

    crc = crc32(final_data)
    return _form_put(
        up_token, key, final_data, params, mime_type,
        crc, hostscache_dir, progress_handler, fname, metadata=metadata
    )


def put_file(
    up_token, key, file_path, params=None,
    mime_type='application/octet-stream', check_crc=False,
    progress_handler=None, upload_progress_recorder=None, keep_last_modified=False, hostscache_dir=None,
    part_size=None, version=None, bucket_name=None, metadata=None
):
    """上传文件到七牛

    Args:
        up_token:                 上传凭证
        key:                      上传文件名
        file_path:                上传文件的路径
        params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
        mime_type:                上传数据的mimeType
        check_crc:                是否校验crc32
        progress_handler:         上传进度
        upload_progress_recorder: 记录上传进度，用于断点续传
        hostscache_dir:           host请求 缓存文件保存位置
        version:                  分片上传版本 目前支持v1/v2版本 默认v1
        part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
        bucket_name:              分片上传v2字段 空间名称
        metadata:                 元数据信息

    Returns:
        一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
        一个ResponseInfo对象
    """
    ret = {}
    size = os.stat(file_path).st_size
    with open(file_path, 'rb') as input_stream:
        file_name = os.path.basename(file_path)
        modify_time = int(os.path.getmtime(file_path))
        if size > get_default('default_upload_threshold'):
            ret, info = put_stream(
                up_token, key, input_stream, file_name, size, hostscache_dir, params,
                mime_type, progress_handler,
                upload_progress_recorder=upload_progress_recorder,
                modify_time=modify_time, keep_last_modified=keep_last_modified,
                part_size=part_size, version=version, bucket_name=bucket_name, metadata=metadata
            )
        else:
            crc = file_crc32(file_path)
            ret, info = _form_put(
                up_token, key, input_stream, params, mime_type,
                crc, hostscache_dir, progress_handler, file_name,
                modify_time=modify_time, keep_last_modified=keep_last_modified, metadata=metadata
            )
    return ret, info


def _form_put(
    up_token,
    key,
    data,
    params,
    mime_type,
    crc,
    hostscache_dir=None,
    progress_handler=None,
    file_name=None,
    modify_time=None,
    keep_last_modified=False,
    metadata=None
):
    bucket_name = Auth.get_bucket_name(up_token)
    uploader = FormUploader(
        bucket_name,
        progress_handler=progress_handler,
        hosts_cache_dir=hostscache_dir
    )

    if modify_time and keep_last_modified:
        metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)

    return uploader.upload(
        key=key,
        data=data,
        data_size=None,
        file_name=file_name,
        modify_time=modify_time,
        mime_type=mime_type,
        metadata=metadata,
        custom_vars=params,
        crc32_int=crc,
        up_token=up_token
    )


def put_stream(
    up_token,
    key,
    input_stream,
    file_name,
    data_size,
    hostscache_dir=None,
    params=None,
    mime_type=None,
    progress_handler=None,
    upload_progress_recorder=None,
    modify_time=None,
    keep_last_modified=False,
    part_size=None,
    version='v1',
    bucket_name=None,
    metadata=None
):
    if not bucket_name:
        bucket_name = Auth.get_bucket_name(up_token)
    if not upload_progress_recorder:
        upload_progress_recorder = UploadProgressRecorder()
    if not version:
        version = 'v1'
    if not part_size:
        part_size = 4 * (1024 * 1024)

    if version == 'v1':
        uploader = ResumeUploaderV1(
            bucket_name,
            progress_handler=progress_handler,
            upload_progress_recorder=upload_progress_recorder,
            hosts_cache_dir=hostscache_dir
        )
        if modify_time and keep_last_modified:
            metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)
    elif version == 'v2':
        uploader = ResumeUploaderV2(
            bucket_name,
            progress_handler=progress_handler,
            upload_progress_recorder=upload_progress_recorder,
            part_size=part_size,
            hosts_cache_dir=hostscache_dir
        )
    else:
        raise ValueError('version only could be v1 or v2')
    return uploader.upload(
        key=key,
        data=input_stream,
        data_size=data_size,
        file_name=file_name,
        modify_time=modify_time,
        mime_type=mime_type,
        metadata=metadata,
        custom_vars=params,
        up_token=up_token
    )
