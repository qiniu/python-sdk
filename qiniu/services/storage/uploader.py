# -*- coding: utf-8 -*-
import os

from typing_extensions import deprecated

from qiniu.config import _BLOCK_SIZE, get_default

from qiniu.auth import Auth
from qiniu.utils import crc32, file_crc32, rfc_from_timestamp

from qiniu.services.storage.uploaders import FormUploader, ResumeUploaderV1, ResumeUploaderV2
from qiniu.services.storage.upload_progress_recorder import UploadProgressRecorder

# for compat to old sdk (<= v7.11.1)
from qiniu.services.storage.legacy import _Resume  # noqa


def put_data(
        up_token,
        key,
        data,
        params=None,
        mime_type='application/octet-stream',
        check_crc=False,
        progress_handler=None,
        fname=None,
        hostscache_dir=None,
        metadata=None,
        regions=None,
        accelerate_uploading=False
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
        fname:            文件名
        hostscache_dir:   host请求 缓存文件保存位置
        metadata:         元数据
        regions:          区域信息，默认自动查询
        accelerate_uploading: 是否优先使用加速上传

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
        up_token=up_token, key=key, data=final_data, params=params, mime_type=mime_type,
        crc=crc, progress_handler=progress_handler, file_name=fname, metadata=metadata,
        regions=regions, accelerate_uploading=accelerate_uploading
    )


@deprecated("use put_file_v2 instead")
def put_file(
        up_token, key, file_path, params=None,
        mime_type='application/octet-stream', check_crc=False,
        progress_handler=None, upload_progress_recorder=None, keep_last_modified=False, hostscache_dir=None,
        part_size=None, version='v1', bucket_name=None, metadata=None,
        regions=None, accelerate_uploading=False
):
    """上传文件到七牛，此接口的分片传接口默认使用 V1，推荐使用 V2，V2 上传效率更高；在一些专有云服务中需要确认服务是否支持 V2。

        Args:
            up_token:                 上传凭证
            key:                      上传文件名
            file_path:                上传文件的路径
            params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
            mime_type:                上传数据的mimeType
            check_crc:                是否校验crc32
            progress_handler:         上传进度
            upload_progress_recorder: 记录上传进度，用于断点续传
            keep_last_modified:       是否保留文件的最后修改时间
            hostscache_dir:           host请求 缓存文件保存位置，已废弃
            version:                  分片上传版本 目前支持v1/v2版本 默认v1
            part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
            bucket_name:              分片上传v2字段 空间名称
            metadata:                 元数据信息
            regions:                  region信息
            accelerate_uploading:     是否开启加速上传

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
    """
    return _put_file(
        up_token=up_token, key=key, file_path=file_path, params=params, mime_type=mime_type,
        check_crc=check_crc, progress_handler=progress_handler, upload_progress_recorder=upload_progress_recorder,
        keep_last_modified=keep_last_modified, part_size=part_size, version=version, bucket_name=bucket_name,
        metadata=metadata, regions=regions, accelerate_uploading=accelerate_uploading
    )


def put_file_v2(
        up_token, key, file_path, params=None,
        mime_type='application/octet-stream', check_crc=False,
        progress_handler=None, upload_progress_recorder=None, keep_last_modified=False,
        part_size=None, version='v2', bucket_name=None, metadata=None,
        regions=None, accelerate_uploading=False
):
    """上传文件到七牛，此接口的分片传接口默认使用 V2，V2 上传效率更高；在一些专有云服务中需要确认服务是否支持 V2。

        Args:
            up_token:                 上传凭证
            key:                      上传文件名
            file_path:                上传文件的路径
            params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
            mime_type:                上传数据的mimeType
            check_crc:                是否校验crc32
            progress_handler:         上传进度
            upload_progress_recorder: 记录上传进度，用于断点续传
            keep_last_modified:       是否保留文件的最后修改时间
            version:                  分片上传版本 目前支持v1/v2版本 默认v1
            part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
            bucket_name:              分片上传v2字段 空间名称
            metadata:                 元数据信息
            regions:                  region信息
            accelerate_uploading:     是否开启加速上传

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
    """
    return _put_file(
        up_token=up_token, key=key, file_path=file_path, params=params, mime_type=mime_type,
        check_crc=check_crc, progress_handler=progress_handler, upload_progress_recorder=upload_progress_recorder,
        keep_last_modified=keep_last_modified, part_size=part_size, version=version, bucket_name=bucket_name,
        metadata=metadata, regions=regions, accelerate_uploading=accelerate_uploading
    )


def _put_file(
        up_token, key, file_path, params=None,
        mime_type='application/octet-stream', check_crc=False,
        progress_handler=None, upload_progress_recorder=None, keep_last_modified=False,
        part_size=None, version=None, bucket_name=None, metadata=None,
        regions=None, accelerate_uploading=False
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
        keep_last_modified:       是否保留文件的最后修改时间
        version:                  分片上传版本 目前支持v1/v2版本 默认v1
        part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
        bucket_name:              分片上传v2字段 空间名称
        metadata:                 元数据信息
        regions:                  region信息
        accelerate_uploading:     是否开启加速上传

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
            ret, info = put_stream_v2(
                up_token=up_token, key=key, input_stream=input_stream, file_name=file_name, data_size=size, params=params,
                mime_type=mime_type, progress_handler=progress_handler,
                upload_progress_recorder=upload_progress_recorder,
                modify_time=modify_time, keep_last_modified=keep_last_modified,
                part_size=part_size, version=version, bucket_name=bucket_name, metadata=metadata,
                regions=regions, accelerate_uploading=accelerate_uploading
            )
        else:
            crc = file_crc32(file_path)
            ret, info = _form_put(
                up_token=up_token, key=key, data=input_stream, params=params, mime_type=mime_type,
                crc=crc, progress_handler=progress_handler, file_name=file_name,
                modify_time=modify_time, keep_last_modified=keep_last_modified, metadata=metadata,
                regions=regions, accelerate_uploading=accelerate_uploading
            )
    return ret, info


def _form_put(
        up_token,
        key,
        data,
        params,
        mime_type,
        crc,
        progress_handler=None,
        file_name=None,
        modify_time=None,
        keep_last_modified=False,
        metadata=None,
        regions=None,
        accelerate_uploading=False
):
    bucket_name = Auth.get_bucket_name(up_token)
    uploader = FormUploader(
        bucket_name,
        progress_handler=progress_handler,
        regions=regions,
        accelerate_uploading=accelerate_uploading,
        preferred_scheme=get_default('default_zone').scheme
    )

    if modify_time and keep_last_modified:
        metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)

    return uploader.upload(
        key=key,
        data=data,
        file_name=file_name,
        modify_time=modify_time,
        mime_type=mime_type,
        metadata=metadata,
        custom_vars=params,
        crc32_int=crc,
        up_token=up_token
    )


@deprecated("use put_stream_v2 instead")
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
        metadata=None,
        regions=None,
        accelerate_uploading=False
):
    """ 通过 stream 方式上传文件到七牛，此接口的分片传接口默认使用 V1，推荐使用 V2，V2 上传效率更高；在一些专有云服务中需要确认服务是否支持 V2。

    Args:
        up_token:                 上传凭证
        key:                      上传文件名
        input_stream:             上传数据流
        file_name:                文件名
        data_size:                数据流大小
        hostscache_dir:           host请求 缓存文件保存位置，当前已废弃
        params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
        mime_type:                上传数据的mimeType
        progress_handler:         上传进度
        upload_progress_recorder: 记录上传进度，用于断点续传
        modify_time:              数据修改时间
        keep_last_modified:       是否保留文件的最后修改时间
        part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
        version:                  分片上传版本 目前支持v1/v2版本 默认v1
        bucket_name:              分片上传v2字段 空间名称
        metadata:                 元数据信息
        regions:                  region信息
        accelerate_uploading:     是否开启加速上传

    Returns:
        一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
        一个ResponseInfo对象
    """
    return _put_stream(
        up_token=up_token,
        key=key,
        input_stream=input_stream,
        file_name=file_name,
        data_size=data_size,
        params=params,
        mime_type=mime_type,
        progress_handler=progress_handler,
        upload_progress_recorder=upload_progress_recorder,
        modify_time=modify_time,
        keep_last_modified=keep_last_modified,
        part_size=part_size,
        version=version,
        bucket_name=bucket_name,
        metadata=metadata,
        regions=regions,
        accelerate_uploading=accelerate_uploading
    )


def put_stream_v2(
        up_token,
        key,
        input_stream,
        file_name,
        data_size,
        params=None,
        mime_type=None,
        progress_handler=None,
        upload_progress_recorder=None,
        modify_time=None,
        keep_last_modified=False,
        part_size=None,
        version='v2',
        bucket_name=None,
        metadata=None,
        regions=None,
        accelerate_uploading=False
):
    """ 通过 stream 方式上传文件到七牛，此接口的分片传接口默认使用 V2，V2 上传效率更高；在一些专有云服务中需要确认服务是否支持 V2。

        Args:
            up_token:                 上传凭证
            key:                      上传文件名
            input_stream:             上传数据流
            file_name:                文件名
            data_size:                数据流大小
            params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
            mime_type:                上传数据的mimeType
            progress_handler:         上传进度
            upload_progress_recorder: 记录上传进度，用于断点续传
            modify_time:              数据修改时间
            keep_last_modified:       是否保留文件的最后修改时间
            part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
            version:                  分片上传版本 目前支持v1/v2版本 默认v1
            bucket_name:              分片上传v2字段 空间名称
            metadata:                 元数据信息
            regions:                  region信息
            accelerate_uploading:     是否开启加速上传

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
    """
    return _put_stream(
        up_token=up_token,
        key=key,
        input_stream=input_stream,
        file_name=file_name,
        data_size=data_size,
        params=params,
        mime_type=mime_type,
        progress_handler=progress_handler,
        upload_progress_recorder=upload_progress_recorder,
        modify_time=modify_time,
        keep_last_modified=keep_last_modified,
        part_size=part_size,
        version=version,
        bucket_name=bucket_name,
        metadata=metadata,
        regions=regions,
        accelerate_uploading=accelerate_uploading
    )


def _put_stream(
        up_token,
        key,
        input_stream,
        file_name,
        data_size,
        params=None,
        mime_type=None,
        progress_handler=None,
        upload_progress_recorder=None,
        modify_time=None,
        keep_last_modified=False,
        part_size=None,
        version='v2',
        bucket_name=None,
        metadata=None,
        regions=None,
        accelerate_uploading=False
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
            regions=regions,
            accelerate_uploading=accelerate_uploading,
            preferred_scheme=get_default('default_zone').scheme
        )
        if modify_time and keep_last_modified:
            metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)
    elif version == 'v2':
        uploader = ResumeUploaderV2(
            bucket_name,
            progress_handler=progress_handler,
            upload_progress_recorder=upload_progress_recorder,
            part_size=part_size,
            regions=regions,
            accelerate_uploading=accelerate_uploading,
            preferred_scheme=get_default('default_zone').scheme
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
