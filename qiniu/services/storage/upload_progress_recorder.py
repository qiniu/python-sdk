# -*- coding: utf-8 -*-

import base64
import json
import os
import tempfile


class UploadProgressRecorder(object):
    """持久化上传记录类

    该类默认保存每个文件的上传记录到文件系统中，用于断点续传
    上传记录为json格式：
    {
        "size": file_size,
        "offset": upload_offset,
        "modify_time": file_modify_time,
        "contexts": contexts
    }

    Attributes:
        record_folder: 保存上传记录的目录
    """
    def __init__(self, record_folder=tempfile.gettempdir()):
        self.record_folder = record_folder

    def get_upload_record(self, key):
        record_file_name = base64.b64encode(key.encode('utf-8')).decode('utf-8')
        upload_record_file_path = os.path.join(self.record_folder,
                                               record_file_name)
        if not os.path.isfile(upload_record_file_path):
            return None
        with open(upload_record_file_path, 'r') as f:
            json_data = json.load(f)
        return json_data

    def set_upload_record(self, key, data):
        record_file_name = base64.b64encode(key.encode('utf-8')).decode('utf-8')
        upload_record_file_path = os.path.join(self.record_folder,
                                               record_file_name)
        with open(upload_record_file_path, 'w') as f:
            json.dump(data, f)

    def delete_upload_record(self, key):
        record_file_name = base64.b64encode(key.encode('utf-8')).decode('utf-8')
        record_file_path = os.path.join(self.record_folder,
                                        record_file_name)
        os.remove(record_file_path)
