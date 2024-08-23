# -*- coding: utf-8 -*-

from qiniu import config
from qiniu import http


class PersistentFop(object):
    """持久化处理类

    该类用于主动触发异步持久化操作，具体规格参考：
    https://developer.qiniu.com/dora/api/persistent-data-processing-pfop

    Attributes:
        auth:       账号管理密钥对，Auth对象
        bucket:     操作资源所在空间
        pipeline:   多媒体处理队列，详见 https://developer.qiniu.com/dora/6499/tasks-and-workflows
        notify_url: 持久化处理结果通知URL
    """

    def __init__(self, auth, bucket, pipeline=None, notify_url=None):
        """初始化持久化处理类"""
        self.auth = auth
        self.bucket = bucket
        self.pipeline = pipeline
        self.notify_url = notify_url

    def execute(self, key, fops, force=None, persistent_type=None):
        """
        执行持久化处理

        Parameters
        ----------
        key: str
            待处理的源文件
        fops: list[str]
            处理详细操作，规格详见 https://developer.qiniu.com/dora/manual/1291/persistent-data-processing-pfop
        force: int or str, optional
            强制执行持久化处理开关
        persistent_type: int or str, optional
            持久化处理类型，为 '1' 时开启闲时任务
        Returns
        -------
        ret: dict
            持久化处理的 persistentId，类似 {"persistentId": 5476bedf7823de4068253bae};
        resp: ResponseInfo
        """
        ops = ';'.join(fops)
        data = {'bucket': self.bucket, 'key': key, 'fops': ops}
        if self.pipeline:
            data['pipeline'] = self.pipeline
        if self.notify_url:
            data['notifyURL'] = self.notify_url
        if force == 1 or force == '1':
            data['force'] = str(force)
        if persistent_type and type(int(persistent_type)) is int:
            data['type'] = str(persistent_type)

        url = '{0}/pfop'.format(config.get_default('default_api_host'))
        return http._post_with_auth(url, data, self.auth)

    def get_status(self, persistent_id):
        """
        获取持久化处理状态

        Parameters
        ----------
        persistent_id: str

        Returns
        -------
        ret: dict
            持久化处理的状态，详见 https://developer.qiniu.com/dora/1294/persistent-processing-status-query-prefop
        resp: ResponseInfo
        """
        url = '{0}/status/get/prefop'.format(config.get_default('default_api_host'))
        data = {
            'id': persistent_id
        }
        return http._get_with_auth(url, data, self.auth)
