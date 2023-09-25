# -*- coding: utf-8 -*-
import hashlib
import os
import time

from qiniu import config, http
from qiniu.auth import Auth
from qiniu.compat import json
from qiniu.utils import _file_iter, crc32, rfc_from_timestamp, urlsafe_base64_encode

from qiniu.services.storage.upload_progress_recorder import UploadProgressRecorder


class _Resume(object):
    """deprecated 断点续上传类

    该类主要实现了分块上传，断点续上，以及相应地创建块和创建文件过程，详细规格参考：
    https://developer.qiniu.com/kodo/api/mkblk
    https://developer.qiniu.com/kodo/api/mkfile

    Attributes:
        up_token:                   上传凭证
        key:                        上传文件名
        input_stream:               上传二进制流
        data_size:                  上传流大小
        params:                     自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
        mime_type:                  上传数据的mimeType
        progress_handler:           上传进度
        upload_progress_recorder:   记录上传进度，用于断点续传
        modify_time:                上传文件修改日期
        hostscache_dir：            host请求 缓存文件保存位置
        version                     分片上传版本 目前支持v1/v2版本 默认v1
        part_size                   分片上传v2必传字段 分片大小范围为1 MB - 1 GB
        bucket_name                 分片上传v2字段 空间名称
    """

    def __init__(self, up_token, key, input_stream, file_name, data_size, hostscache_dir, params, mime_type,
                 progress_handler, upload_progress_recorder, modify_time, keep_last_modified, part_size=None,
                 version=None, bucket_name=None, metadata=None):
        """初始化断点续上传"""
        self.up_token = up_token
        self.key = key
        self.input_stream = input_stream
        self.file_name = file_name
        self.size = data_size
        self.hostscache_dir = hostscache_dir
        self.blockStatus = []
        self.params = params
        self.mime_type = mime_type
        self.progress_handler = progress_handler
        self.upload_progress_recorder = upload_progress_recorder or UploadProgressRecorder()
        self.modify_time = modify_time or time.time()
        self.keep_last_modified = keep_last_modified
        self.version = version or 'v1'
        self.part_size = part_size or config._BLOCK_SIZE
        self.bucket_name = bucket_name
        self.metadata = metadata

    def record_upload_progress(self, offset):
        record_data = {
            'size': self.size,
            'offset': offset,
        }
        if self.version == 'v1':
            record_data['contexts'] = [
                {
                    'ctx': block['ctx'],
                    'expired_at': block['expired_at'] if 'expired_at' in block else 0
                } for block in self.blockStatus
            ]
        elif self.version == 'v2':
            record_data['etags'] = self.blockStatus
            record_data['expired_at'] = self.expiredAt
            record_data['upload_id'] = self.uploadId
        if self.modify_time:
            record_data['modify_time'] = self.modify_time
        self.upload_progress_recorder.set_upload_record(self.file_name, self.key, record_data)

    def recovery_from_record(self):
        record = self.upload_progress_recorder.get_upload_record(self.file_name, self.key)
        if not record:
            if self.version == 'v1':
                return 0
            elif self.version == 'v2':
                return 0, None, None
        try:
            if not record['modify_time'] or record['size'] != self.size or \
                   record['modify_time'] != self.modify_time:
                if self.version == 'v1':
                    return 0
                elif self.version == 'v2':
                    return 0, None, None
        except KeyError:
            if self.version == 'v1':
                return 0
            elif self.version == 'v2':
                return 0, None, None
        if self.version == 'v1':
            if not record.__contains__('contexts') or len(record['contexts']) == 0:
                return 0
            self.blockStatus = [
                # 兼容旧版本的 ctx 持久化 ≤v7.10.0
                ctx if type(ctx) is dict else {'ctx': ctx, 'expired_at': 0}
                for ctx in record['contexts']
            ]
            return record['offset']
        elif self.version == 'v2':
            if not record.__contains__('etags') or len(record['etags']) == 0 or \
               not record.__contains__('expired_at') or float(record['expired_at']) < time.time() or \
               not record.__contains__('upload_id'):
                return 0, None, None
            self.blockStatus = record['etags']
            return record['offset'], record['upload_id'], record['expired_at']

    def upload(self):
        """上传操作"""
        if self.version == 'v1':
            return self._upload_v1()
        elif self.version == 'v2':
            return self._upload_v2()
        else:
            raise ValueError("version must choose v1 or v2 !")

    def _upload_v1(self):
        self.blockStatus = []
        self.recovery_index = 1
        self.expiredAt = None
        self.uploadId = None
        self.get_bucket()
        self.part_size = config._BLOCK_SIZE

        host = self.get_up_host()
        offset = self.recovery_from_record()
        is_resumed = offset > 0

        # 检查原来的分片是否过期，如有则重传该分片
        for index, block_status in enumerate(self.blockStatus):
            if block_status.get('expired_at', 0) > time.time():
                self.input_stream.seek(self.part_size, os.SEEK_CUR)
            else:
                block = self.input_stream.read(self.part_size)
                response, ok = self._make_block_with_retry(block, host)
                ret, info = response
                if not ok:
                    return ret, info
                self.blockStatus[index] = ret
            self.record_upload_progress(offset)

        # 从断点位置上传
        for block in _file_iter(self.input_stream, self.part_size, offset):
            length = len(block)
            response, ok = self._make_block_with_retry(block, host)
            ret, info = response
            if not ok:
                return ret, info

            self.blockStatus.append(ret)
            offset += length
            self.record_upload_progress(offset)
            if callable(self.progress_handler):
                self.progress_handler(((len(self.blockStatus) - 1) * self.part_size) + len(block), self.size)

        ret, info = self.make_file(host)
        if info.status_code == 200 or info.status_code == 701:
            self.upload_progress_recorder.delete_upload_record(self.file_name, self.key)
        if info.status_code == 701 and is_resumed:
            return self.upload()
        return ret, info

    def _upload_v2(self):
        self.blockStatus = []
        self.recovery_index = 1
        self.expiredAt = None
        self.uploadId = None
        self.get_bucket()
        host = self.get_up_host()

        offset, self.uploadId, self.expiredAt = self.recovery_from_record()
        is_resumed = False
        if offset > 0 and self.blockStatus != [] and self.uploadId is not None \
           and self.expiredAt is not None:
            self.recovery_index = self.blockStatus[-1]['partNumber'] + 1
            is_resumed = True
        else:
            self.recovery_index = 1
            init_url = self.block_url_v2(host, self.bucket_name)
            self.uploadId, self.expiredAt = self.init_upload_task(init_url)

        for index, block in enumerate(_file_iter(self.input_stream, self.part_size, offset)):
            length = len(block)
            index_ = index + self.recovery_index
            url = self.block_url_v2(host, self.bucket_name) + '/%s/%d' % (self.uploadId, index_)
            ret, info = self.make_block_v2(block, url)
            if info.status_code == 612:
                self.upload_progress_recorder.delete_upload_record(self.file_name, self.key)
            if info.status_code == 612 and is_resumed:
                return self.upload()
            if ret is None and not info.need_retry():
                return ret, info
            if info.connect_failed():
                if config.get_default('default_zone').up_host_backup:
                    host = config.get_default('default_zone').up_host_backup
                else:
                    host = config.get_default('default_zone')\
                        .get_up_host_backup_by_token(self.up_token, self.hostscache_dir)

            if info.need_retry():
                url = self.block_url_v2(host, self.bucket_name) + '/%s/%d' % (self.uploadId, index + 1)
                ret, info = self.make_block_v2(block, url)
                if info.status_code == 612:
                    self.upload_progress_recorder.delete_upload_record(self.file_name, self.key)
                if info.status_code == 612 and is_resumed:
                    return self.upload()
                if ret is None:
                    return ret, info
            del ret['md5']
            ret['partNumber'] = index_
            self.blockStatus.append(ret)
            offset += length
            self.record_upload_progress(offset)
            if callable(self.progress_handler):
                self.progress_handler(((len(self.blockStatus) - 1) * self.part_size) + len(block), self.size)

        make_file_url = self.block_url_v2(host, self.bucket_name) + '/%s' % self.uploadId
        ret, info = self.make_file_v2(
            self.blockStatus,
            make_file_url,
            self.file_name,
            self.mime_type,
            self.params,
            self.metadata)
        if info.status_code == 200 or info.status_code == 612:
            self.upload_progress_recorder.delete_upload_record(self.file_name, self.key)
        if info.status_code == 612 and is_resumed:
            return self.upload()
        return ret, info

    def make_file_v2(self, block_status, url, file_name=None, mime_type=None, customVars=None, metadata=None):
        """completeMultipartUpload"""
        parts = self.get_parts(block_status)
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'parts': parts,
            'fname': file_name,
            'mimeType': mime_type,
            'customVars': customVars,
            'metadata': metadata
        }
        return self.post_with_headers(url, json.dumps(data), headers=headers)

    def get_up_host(self):
        if config.get_default('default_zone').up_host:
            host = config.get_default('default_zone').up_host
        else:
            host = config.get_default('default_zone').get_up_host_by_token(self.up_token, self.hostscache_dir)
        return host

    def _make_block_with_retry(self, block_data, up_host):
        length = len(block_data)
        crc = crc32(block_data)
        ret, info = self.make_block(block_data, length, up_host)
        if ret is None and not info.need_retry():
            return (ret, info), False
        if info.connect_failed():
            if config.get_default('default_zone').up_host_backup:
                up_host = config.get_default('default_zone').up_host_backup
            else:
                up_host = config.get_default('default_zone') \
                    .get_up_host_backup_by_token(self.up_token, self.hostscache_dir)
            if info.need_retry() or crc != ret['crc32']:
                ret, info = self.make_block(block_data, length, up_host)
                if ret is None or crc != ret['crc32']:
                    return (ret, info), False
        return (ret, info), True

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
        encoded_object_name = urlsafe_base64_encode(self.key) if self.key is not None else '~'
        return '{0}/buckets/{1}/objects/{2}/uploads'.format(host, bucket_name, encoded_object_name)

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

        if self.modify_time and self.keep_last_modified:
            url.append(
                "x-qn-meta-!Last-Modified/{0}".format(urlsafe_base64_encode(rfc_from_timestamp(self.modify_time))))

        if self.metadata:
            for k, v in self.metadata.items():
                if k.startswith('x-qn-meta-'):
                    url.append(
                        "{0}/{1}".format(k, urlsafe_base64_encode(v)))

        url = '/'.join(url)
        return url

    def make_file(self, host):
        """创建文件"""
        url = self.file_url(host)
        body = ','.join([status['ctx'] for status in self.blockStatus])
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

    def get_bucket(self):
        if not self.bucket_name:
            bucket_name = Auth.get_bucket_name(self.up_token)
            if bucket_name:
                self.bucket_name = bucket_name
