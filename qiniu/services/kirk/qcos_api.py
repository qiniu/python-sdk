# -*- coding: utf-8 -*-

from qiniu import config, http
from .config import KIRK_HOST

class QcosClient(object):
    """资源管理客户端

    使用应用密钥生成资源管理客户端，可以进一步：
    1、部署服务和容器，获得信息
    2、创建网络资源，获得信息

    属性：
        auth: 应用密钥对，QiniuMacAuth对象
        host: API host，在『内网模式』下使用时，auth=None，会自动使用 apiproxy 服务，只能管理当前容器所在的应用资源。

    接口：
        list_stacks()
        # create_stack(args)
        # delete_stack(stack)

        list_services(stack)
        # create_service(stack, args)
        # get_service_inspect(stack, service)
        # update_service(stack, service, args)
        # scale_service(stack, service, args)
        # delete_service(stack, service)

        # list_containers(args)
        # get_container_inspect(ip)
        # start_container(ip)
        # stop_container(ip)
        # restart_container(ip)

        # list_aps()
        # create_ap(args)
        # search_ap(mode, args)
        # get_ap(id)
        # set_ap_port(id, port, args)
        # delete_ap(id)

    """

    def __init__(self, auth, host=None):
        self.auth = auth
        if (auth is None):
            self.host = KIRK_HOST['APIPROXY']
        else:
            self.host = host

    def list_stacks(self):
        """获得服务组列表

        """

        url = '{0}/v3/stacks'.format(self.host)
        return http._get_with_qiniu_mac(url, None, self.auth)

    def list_services(self, stack):
        """获得服务列表

        """

        url = '{0}/v3/stacks/{1}/services'.format(self.host, stack)
        return http._get_with_qiniu_mac(url, None, self.auth)
