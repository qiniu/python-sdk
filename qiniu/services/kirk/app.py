# -*- coding: utf-8 -*-

from qiniu import config, http, QiniuMacAuth
from .config import KIRK_HOST
from .qcos_api import QcosClient

class AccountClient(object):
    """客户端入口

    使用账号密钥生成账号客户端，可以进一步：
    1、获取和操作账号数据
    2、获得部署的应用的客户端

    属性：
        auth: 账号管理密钥对，QiniuMacAuth对象
        host: API host，在『内网模式』下使用时，auth=None，会自动使用 apiproxy 服务

    接口：
        get_qcos_client(app_uri)
        create_qcos_client(app_uri)
        get_app_keys(app_uri)
        get_valid_app_auth(app_uri)
        get_account_info()
        get_app_region_products(app_uri)
        get_region_products(region)
        list_regions()
        list_apps()
        create_app(args)
        delete_app(app_uri)

    """

    def __init__(self, auth, host=None):
        self.auth = auth
        self.qcos_clients = {}
        if (auth is None):
            self.host = KIRK_HOST['APPPROXY']
        else:
            self.host = KIRK_HOST['APPGLOBAL']
        acc, info = self.get_account_info()
        self.uri = acc.get('name')

    def get_qcos_client(self, app_uri):
        """获得资源管理客户端
        缓存，但不是线程安全的
        """

        client = self.qcos_clients.get(app_uri)
        if (client is None):
            client = self.create_qcos_client(app_uri)
            self.qcos_clients[app_uri] = client

        return client

    def create_qcos_client(self, app_uri):
        """创建资源管理客户端

        """

        if (self.auth is None):
            return QcosClient(None)

        products = self.get_app_region_products(app_uri)
        auth = self.get_valid_app_auth(app_uri)

        if products is None or auth is None:
            return None

        return QcosClient(auth, products.get('api'))

    def get_app_keys(self, app_uri):
        """获得账号下应用的密钥

        """

        url = '{0}/v3/apps/{1}/keys'.format(self.host, app_uri)
        return http._get_with_qiniu_mac(url, None, self.auth)

    def get_valid_app_auth(self, app_uri):
        """获得账号下可用的应用的密钥

        """

        ret, retInfo = self.get_app_keys(app_uri)

        if ret is None:
            return None

        for k in ret:
            if (k.get('state') == 'enabled'):
                return QiniuMacAuth(k.get('ak'), k.get('sk'))

        return None

    def get_account_info(self):
        """获得当前账号的信息

        """

        url = '{0}/v3/info'.format(self.host)
        return http._get_with_qiniu_mac(url, None, self.auth)

    def get_app_region_products(self, app_uri):
        """获得指定应用所在区域的产品信息

        """
        apps, retInfo = self.list_apps()
        if apps is None:
            return None

        for app in apps:
            if (app.get('uri') == app_uri):
                return self.get_region_products(app.get('region'))

        return

    def get_region_products(self, region):
        """获得指定区域的产品信息

        """

        regions, retInfo = self.list_regions()
        if regions is None:
            return None

        for r in regions:
            if r.get('name') == region:
                return r.get('products')

    def list_regions(self):
        """获得账号可见的区域的信息

        """

        url = '{0}/v3/regions'.format(self.host)
        return http._get_with_qiniu_mac(url, None, self.auth)

    def list_apps(self):
        """获得当前账号的应用列表

        """

        url = '{0}/v3/apps'.format(self.host)
        return http._get_with_qiniu_mac(url, None, self.auth)

    def  create_app(self, args):
        """创建应用

        """

        url = '{0}/v3/apps'.format(self.host)
        return http._post_with_qiniu_mac(url, args, self.auth)

    def  delete_app(self, app_uri):
        """删除应用

        """

        url = '{0}/v3/apps/{1}'.format(self.host, app_uri)
        return http._delete_with_qiniu_mac(url, None, self.auth)
