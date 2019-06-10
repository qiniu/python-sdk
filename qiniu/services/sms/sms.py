# -*- coding: utf-8 -*-

from qiniu import http
import json


class Sms(object):
    def __init__(self, auth):
        self.auth = auth
        self.server = 'https://sms.qiniuapi.com'

    def createSignature(self, signature, source, pics=None):
        """
        *创建签名
        *signature: string类型，必填，【长度限制8个字符内】超过长度会报错
        *source: string类型，必填，申请签名时必须指定签名来源。取值范围为：
            enterprises_and_institutions 企事业单位的全称或简称
            website 工信部备案网站的全称或简称
            app APP应用的全称或简称
            public_number_or_small_program 公众号或小程序的全称或简称
            store_name 电商平台店铺名的全称或简称
            trade_name 商标名的全称或简称
        *pics: 签名对应的资质证明图片进行 base64 编码格式转换后的字符串
        * @ return: 类型array
        {
            "signature_id": < signature_id >
        }
        """
        req = {}
        req['signature'] = signature
        req['source'] = source
        if pics:
            req['pics'] = pics
        body = json.dumps(req)
        url = '{0}/v1/signature'.format(self.server)
        return self.__post(url, body)

    def querySignature(self, audit_status=None, page=1, page_size=20):
        """
        查询签名
        * audit_status: 审核状态 string 类型，可选，取值范围为: "passed"(通过), "rejected"(未通过), "reviewing"(审核中)
        * page:页码 int  类型，
        * page_size: 分页大小 int 类型，可选， 默认为20
        *@return: 类型array {
            "items": [{
            "id": string,
            "signature": string,
            "source": string,
            "audit_status": string,
            "reject_reason": string,
            "created_at": int64,
            "updated_at": int64
                }...],
            "total": int,
            "page": int,
            "page_size": int,
            }
        """
        url = '{}/v1/signature'.format(self.server)
        if audit_status:
            url = '{}?audit_status={}&page={}&page_size={}'.format(url, audit_status, page, page_size)
        else:
            url = '{}?page={}&page_size={}'.format(url, page, page_size)
        return self.__get(url)

    def updateSignature(self, id, signature):
        """
        编辑签名
        *  id 签名id : string 类型，必填，
        * signature: string 类型，必填，
        request 类型array {
        "signature": string
        }
        :return:
        """
        url = '{}/v1/signature/{}'.format(self.server, id)
        req = {}
        req['signature'] = signature
        body = json.dumps(req)
        return self.__put(url, body)

    def deleteSignature(self, id):

        """
        删除辑签名
        *  id 签名id : string 类型，必填，
        * @retrun : 请求成功 HTTP 状态码为 200

        """
        url = '{}/v1/signature/{}'.format(self.server, id)
        return self.__delete(url)

    def createTemplate(self, name, template, type, description, signature_id):
        """
        创建模版
        :param name: 模板名称 string 类型 ，必填
        :param template: 模板内容 string  类型，必填
        :param type: 模板类型 string 类型，必填，
                    取值范围为: notification (通知类短信), verification (验证码短信), marketing (营销类短信)
        :param description: 申请理由简述 string  类型，必填
        :param signature_id: 已经审核通过的签名 string  类型，必填
        :return: 类型 array {
        "template_id": string
                }
        """
        url = '{}/v1/template'.format(self.server)
        req = {}
        req['name'] = name
        req['template'] = template
        req['type'] = type
        req['description'] = description
        req['signature_id'] = signature_id
        body = json.dumps(req)
        return self.__post(url, body)

    def queryTemplate(self, audit_status, page=1, page_size=20):
        """
        查询模版
        :param audit_status: 审核状态, 取值范围为: passed (通过), rejected (未通过), reviewing (审核中)
        :param page: 页码。默认为 1
        :param page_size: 分页大小。默认为 20
        :return:{
        "items": [{
            "id": string,
            "name": string,
            "template": string,
            "audit_status": string,
            "reject_reason": string,
            "type": string,
            "signature_id": string, // 模版绑定的签名ID
            "signature_text": string, // 模版绑定的签名内容
            "created_at": int64,
            "updated_at": int64
            }...],
            "total": int,
            "page": int,
            "page_size": int
        }
        """
        url = '{}/v1/template'.format(self.server)
        if audit_status:
            url = '{}?audit_status={}&page={}&page_size={}'.format(url, audit_status, page, page_size)
        else:
            url = '{}?page={}&page_size={}'.format(url, page, page_size)
        return self.__get(url)

    def updateTemplate(self, id, name, template, description, signature_id):
        """
        更新模版
        :param id: template_id
        :param name: 模板名称 string 类型 ，必填
        :param template: 模板内容 string  类型，必填
        :param description: 申请理由简述 string  类型，必填
        :param signature_id: 已经审核通过的签名 string  类型，必填
        :return: 请求成功 HTTP 状态码为 200
        """
        url = '{}/v1/template/{}'.format(self.server, id)
        req = {}
        req['name'] = name
        req['template'] = template
        req['description'] = description
        req['signature_id'] = signature_id
        body = json.dumps(req)
        return self.__put(url, body)

    def deleteTemplate(self, id):
        """
        删除模版
        :param id: template_id
        :return: 请求成功 HTTP 状态码为 200
        """
        url = '{}/v1/template/{}'.format(self.server, id)
        return self.__delete(url)

    def sendMessage(self, template_id, mobiles, parameters):
        """
        发送短信
        :param template_id:  模板 ID
        :param mobiles: 手机号
        :param parameters: 自定义魔法变量，变量设置在创建模板时，参数template指定
        :return:{
            "job_id": string
        }
        """
        url = '{}/v1/message'.format(self.server)
        req = {}
        req['template_id'] = template_id
        req['mobiles'] = mobiles
        req['parameters'] = parameters
        body = json.dumps(req)
        return self.__post(url, body)

    def __post(self, url, data=None):
        headers = {'Content-Type': 'application/json'}
        return http._post_with_qiniu_mac_and_headers(url, data, self.auth, headers)

    def __get(self, url, params=None):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        return http._get_with_qiniu_mac_and_headers(url, params, self.auth, headers)

    def __put(self, url, data=None):
        headers = {'Content-Type': 'application/json'}
        return http._put_with_qiniu_mac_and_headers(url, data, self.auth, headers)

    def __delete(self, url, data=None):
        headers = {'Content-Type': 'application/json'}
        return http._delete_with_qiniu_mac_and_headers(url, data, self.auth, headers)
