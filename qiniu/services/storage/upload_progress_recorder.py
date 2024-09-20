# -*- coding: utf-8 -*-
import hashlib
import json
import os
import tempfile
from qiniu.compat import is_py2


class UploadProgressRecorder(object):
    """
    持久化上传记录类

    该类默认保存每个文件的上传记录到文件系统中，用于断点续传
    上传记录为json格式

    Attributes:
        record_folder: 保存上传记录的目录
    """

    def __init__(self, record_folder=tempfile.gettempdir()):
        self.record_folder = record_folder

    def __get_upload_record_file_path(self, file_name, key):
        record_key = '{0}/{1}'.format(key, file_name)
        if is_py2:
            record_file_name = hashlib.md5(record_key).hexdigest()
        else:
            record_file_name = hashlib.md5(record_key.encode('utf-8')).hexdigest()
        return os.path.join(self.record_folder, record_file_name)

    def has_upload_record(self, file_name, key):
        upload_record_file_path = self.__get_upload_record_file_path(file_name, key)
        return os.path.isfile(upload_record_file_path)

    def get_upload_record(self, file_name, key):
        upload_record_file_path = self.__get_upload_record_file_path(file_name, key)
        if not self.has_upload_record(file_name, key):
            return None
        try:
            with open(upload_record_file_path, 'r') as f:
                json_data = json.load(f)
        except (IOError, ValueError):
            json_data = None

        return json_data

    def set_upload_record(self, file_name, key, data):
        upload_record_file_path = self.__get_upload_record_file_path(file_name, key)
        with open(upload_record_file_path, 'w') as f:
            json.dump(data, f)

    def delete_upload_record(self, file_name, key):
        upload_record_file_path = self.__get_upload_record_file_path(file_name, key)
        try:
            os.remove(upload_record_file_path)
        except OSError:
            pass
