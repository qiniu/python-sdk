# -*- coding: utf-8 -*-

import hashlib
import json
import os
import time

from qiniu import config
from qiniu.utils import urlsafe_base64_encode, crc32, file_crc32, _file_iter, rfc_from_timestamp
from qiniu import http
from .upload_progress_recorder import UploadProgressRecorder


def put_data(
        up_token, key, data, params=None, mime_type='application/octet-stream', check_crc=False, progress_handler=None,
        fname=None, hostscache_dir=None):
    """上传二进制流到七牛

    Args:
        up_token:         上传凭证
        key:              上传文件名
        data:             上传二进制流
        params:           自定义变量，规格参考 http://developer.qiniu.com/docs/v6/api/overview/up/response/vars.html#xvar
        mime_type:        上传数据的mimeType
        check_crc:        是否校验crc32
        progress_handler: 上传进度
        hostscache_dir：  host请求 缓存文件保存位置

    Returns:
        一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
        一个ResponseInfo对象
    """
    final_data = b''
    if hasattr(data, 'read'):
        while True:
            tmp_data = data.read(config._BLOCK_SIZE)
            if len(tmp_data) == 0:
                break
            else:
                final_data += tmp_data
    else:
        final_data = data

    crc = crc32(final_data)
    return _form_put(up_token, key, final_data, params, mime_type, crc, hostscache_dir, progress_handler, fname)


def put_file(up_token, key, file_path, params=None,
             mime_type='application/octet-stream', check_crc=False,
             progress_handler=None, upload_progress_recorder=None, keep_last_modified=False, hostscache_dir=None):
    """上传文件到七牛

    Args:
        up_token:                 上传凭证
        key:                      上传文件名
        file_path:                上传文件的路径
        params:                   自定义变量，规格参考 http://developer.qiniu.com/docs/v6/api/overview/up/response/vars.html#xvar
        mime_type:                上传数据的mimeType
        check_crc:                是否校验crc32
        progress_handler:         上传进度
        upload_progress_recorder: 记录上传进度，用于断点续传
        hostscache_dir：          host请求 缓存文件保存位置

    Returns:
        一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
        一个ResponseInfo对象
    """
    ret = {}
    size = os.stat(file_path).st_size
    with open(file_path, 'rb') as input_stream:
        file_name = os.path.basename(file_path)
        modify_time = int(os.path.getmtime(file_path))
        if size > config._BLOCK_SIZE * 2:
            ret, info = put_stream(up_token, key, input_stream, file_name, size, hostscache_dir, params,
                                   mime_type, progress_handler,
                                   upload_progress_recorder=upload_progress_recorder,
                                   modify_time=modify_time, keep_last_modified=keep_last_modified)
        else:
            crc = file_crc32(file_path)
            ret, info = _form_put(up_token, key, input_stream, params, mime_type,
                                  crc, hostscache_dir, progress_handler, file_name,
                                  modify_time=modify_time, keep_last_modified=keep_last_modified)
    return ret, info


def _form_put(up_token, key, data, params, mime_type, crc, hostscache_dir=None, progress_handler=None, file_name=None,
              modify_time=None,
              keep_last_modified=False):
    fields = {}
    if params:
        for k, v in params.items():
            fields[k] = str(v)
    if crc:
        fields['crc32'] = crc
    if key is not None:
        fields['key'] = key

    fields['token'] = up_token
    if config.get_default('default_zone').up_host:
        url = config.get_default('default_zone').up_host
    else:
        url = config.get_default('default_zone').get_up_host_by_token(up_token, hostscache_dir)
    # name = key if key else file_name

    fname = file_name
    if not fname or not fname.strip():
        fname = 'file_name'

    # last modify time
    if modify_time and keep_last_modified:
        fields['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)

    r, info = http._post_file(url, data=fields, files={'file': (fname, data, mime_type)})
    if r is None and info.need_retry():
        if info.connect_failed:
            if config.get_default('default_zone').up_host_backup:
                url = config.get_default('default_zone').up_host_backup
            else:
                url = config.get_default('default_zone').get_up_host_backup_by_token(up_token, hostscache_dir)
        if hasattr(data, 'read') is False:
            pass
        elif hasattr(data, 'seek') and (not hasattr(data, 'seekable') or data.seekable()):
            data.seek(0)
        else:
            return r, info
        r, info = http._post_file(url, data=fields, files={'file': (fname, data, mime_type)})

    return r, info


def put_stream(up_token, key, input_stream, file_name, data_size, hostscache_dir=None, params=None,
               mime_type=None, progress_handler=None,
               upload_progress_recorder=None, modify_time=None, keep_last_modified=False,
               part_size=None, version=None, bucket_name=None):
    task = _Resume(up_token, key, input_stream, file_name, data_size, hostscache_dir, params, mime_type,
                   progress_handler, upload_progress_recorder, modify_time, keep_last_modified,
                   part_size, version, bucket_name)
    return task.upload()


class _Resume(object):
    """断点续上传类

    该类主要实现了分块上传，断点续上，以及相应地创建块和创建文件过程，详细规格参考：
    http://developer.qiniu.com/docs/v6/api/reference/up/mkblk.html
    http://developer.qiniu.com/docs/v6/api/reference/up/mkfile.html

    Attributes:
        up_token:                   上传凭证
        key:                        上传文件名
        input_stream:               上传二进制流
        data_size:                  上传流大小
        params:                     自定义变量，规格参考 http://developer.qiniu.com/docs/v6/api/overview/up/response/vars.html#xvar
        mime_type:                  上传数据的mimeType
        progress_handler:           上传进度
        upload_progress_recorder:   记录上传进度，用于断点续传
        modify_time:                上传文件修改日期
        hostscache_dir：            host请求 缓存文件保存位置
        version                     分片上传版本 目前支持v1/v2版本 默认v1
        part_size                   分片上传v2必传字段 分片大小范围为1 MB - 1 GB
        bucket_name                 分片上传v2字段必传字段 空间名称
    """

    def __init__(self, up_token, key, input_stream, file_name, data_size, hostscache_dir, params, mime_type,
                 progress_handler, upload_progress_recorder, modify_time, keep_last_modified, part_size=None,
                 version=None, bucket_name=None):
        """初始化断点续上传"""
        self.up_token = up_token
        self.key = key
        self.input_stream = input_stream
        self.file_name = file_name
        self.size = data_size
        self.hostscache_dir = hostscache_dir
        self.params = params
        self.mime_type = mime_type
        self.progress_handler = progress_handler
        self.upload_progress_recorder = upload_progress_recorder or UploadProgressRecorder()
        self.modify_time = modify_time or time.time()
        self.keep_last_modified = keep_last_modified
        self.version = version or 'v1'
        self.part_size = part_size
        self.bucket_name = bucket_name

    def record_upload_progress(self, offset):
        record_data = {
            'size': self.size,
            'offset': offset,
        }
        if self.version == 'v1':
            record_data['contexts'] = [block['ctx'] for block in self.blockStatus]
        elif self.version == 'v2':
            if self.expiredAt > time.time():
                record_data['etags'] = self.blockStatus
        if self.modify_time:
            record_data['modify_time'] = self.modify_time
        self.upload_progress_recorder.set_upload_record(self.file_name, self.key, record_data)

    def recovery_from_record(self):
        record = self.upload_progress_recorder.get_upload_record(self.file_name, self.key)
        if not record:
            return 0
        try:
            if not record['modify_time'] or record['size'] != self.size or \
                   record['modify_time'] != self.modify_time:
                return 0
        except KeyError:
            return 0
        if self.version == 'v1':
            self.blockStatus = [{'ctx': ctx} for ctx in record['contexts']]
        elif self.version == 'v2':
            self.blockStatus = record['etags']
        return record['offset']

    def upload(self, metadata=None):
        """上传操作"""
        self.blockStatus = []
        self.recovery_index = 1
        self.expiredAt = 1
        host = self.get_up_host()
        offset = self.recovery_from_record()
        if self.version == 'v1':
            self.part_size = config._BLOCK_SIZE
        elif self.version == 'v2':
            if offset > 0 and self.blockStatus != []:
                self.recovery_index = self.blockStatus[-1]['partNumber'] + 1
            else:
                self.recovery_index = 1
            init_url = self.block_url_v2(host, self.bucket_name)
            upload_id, self.expiredAt = self.init_upload_task(init_url)
        else:
            raise ValueError("version must choose v1 or v2 !")
        for index, block in enumerate(_file_iter(self.input_stream, self.part_size, offset)):
            length = len(block)
            if self.version == 'v1':
                ret, info = self.make_block(block, length, host)
            elif self.version == 'v2':
                index_ = index + self.recovery_index
                url = init_url + '/%s/%d' % (upload_id, index_)
                ret, info = self.make_block_v2(block, url)
            if ret is None and not info.need_retry():
                return ret, info
            if info.connect_failed():
                if config.get_default('default_zone').up_host_backup:
                    host = config.get_default('default_zone').up_host_backup
                else:
                    host = config.get_default('default_zone').get_up_host_backup_by_token(self.up_token,
                                                                                          self.hostscache_dir)
            if self.version == 'v1':
                if info.need_retry():
                    ret, info = self.make_block(block, length, host)
                    if ret is None:
                        return ret, info
            elif self.version == 'v2':
                if info.need_retry():
                    url = self.block_url_v2(host, self.bucket_name) + '/%s/%d' % (upload_id, index + 1)
                    ret, info = self.make_block_v2(block, url)
                    if ret is None:
                        return ret, info
                del ret['md5']
                ret['partNumber'] = index_
            self.blockStatus.append(ret)
            offset += length
            self.record_upload_progress(offset)
            if (callable(self.progress_handler)):
                self.progress_handler(((len(self.blockStatus) - 1) * self.part_size) + len(block), self.size)
        if self.version == 'v1':
            return self.make_file(host)
        elif self.version == 'v2':
            make_file_url = self.block_url_v2(host, self.bucket_name) + '/%s' % upload_id
            return self.make_file_v2(self.blockStatus, make_file_url, self.file_name,
                                     self.mime_type, metadata, self.params)

    def make_file_v2(self, block_status, url, file_name=None, mime_type=None,
                     metadata=None, customVars=None):
        """completeMultipartUpload"""
        parts = self.get_parts(block_status)
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'parts': parts,
            'fname': file_name,
            'mimeType': mime_type,
            'metadata': metadata,
            'customVars': customVars
        }
        ret, info = self.post_with_headers(url, json.dumps(data), headers=headers)
        return ret, info

    def get_up_host(self):
        if config.get_default('default_zone').up_host:
            host = config.get_default('default_zone').up_host
        else:
            host = config.get_default('default_zone').get_up_host_by_token(self.up_token, self.hostscache_dir)
        return host

    def make_block(self, block, block_size, host):
        """创建块"""
        url = self.block_url(host, block_size)
        return self.post(url, block)

    def make_block_v2(self, block, url):
        headers = {
            'Content-Type': 'application/octet-stream',
            'Content-MD5': hashlib.md5(block).hexdigest(),
        }
        return self.put(url, block, headers)

    def block_url(self, host, size):
        return '{0}/mkblk/{1}'.format(host, size)

    def block_url_v2(self, host, bucket_name):
        encode_object_name = urlsafe_base64_encode(self.key) if self.key is not None else '～'
        return '{0}/buckets/{1}/objects/{2}/uploads'.format(host, bucket_name, encode_object_name)

    def file_url(self, host):
        url = ['{0}/mkfile/{1}'.format(host, self.size)]
        if self.mime_type:
            url.append('mimeType/{0}'.format(urlsafe_base64_encode(self.mime_type)))

        if self.key is not None:
            url.append('key/{0}'.format(urlsafe_base64_encode(self.key)))

        if self.file_name is not None:
            url.append('fname/{0}'.format(urlsafe_base64_encode(self.file_name)))

        if self.params:
            for k, v in self.params.items():
                url.append('{0}/{1}'.format(k, urlsafe_base64_encode(v)))
            pass

        if self.modify_time and self.keep_last_modified:
            url.append(
                "x-qn-meta-!Last-Modified/{0}".format(urlsafe_base64_encode(rfc_from_timestamp(self.modify_time))))

        url = '/'.join(url)
        return url

    def make_file(self, host):
        """创建文件"""
        url = self.file_url(host)
        body = ','.join([status['ctx'] for status in self.blockStatus])
        self.upload_progress_recorder.delete_upload_record(self.file_name, self.key)
        return self.post(url, body)

    def init_upload_task(self, url):
        body, resp = self.post(url, '')
        if body is not None:
            return body['uploadId'], body['expireAt']
        else:
            return None, None

    def post(self, url, data):
        return http._post_with_token(url, data, self.up_token)

    def post_with_headers(self, url, data, headers):
        return http._post_with_token_and_headers(url, data, self.up_token, headers)

    def put(self, url, data, headers):
        return http._put_with_token_and_headers(url, data, self.up_token, headers)

    def get_parts(self, block_status):
        return sorted(block_status, key=lambda i: i['partNumber'])
