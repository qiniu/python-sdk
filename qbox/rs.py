#coding=utf8

import config
import fileop
from base64 import urlsafe_b64encode

class Service:
    """
     * Qiniu Resource Storage (Key-Value) Service
     * 资源存储(键值对)。基本特性为：每个账户可创建多个表，每个表包含多个键值对(Key-Value对)，Key是任意的字符串，Value是一个文件。
    """

    def __init__(self, conn, bucket = ''):
        self.Conn = conn
        self.BucketName = bucket

    def PutAuth(self):
        """
         * func PutAuth() => PutAuthRet
         * 上传授权（生成一个短期有效的可匿名上传URL）
        """
        url = config.IO_HOST + '/put-auth/'
        return self.Conn.Call(url)

    def PutAuthEx(self, expires, cbUrl):
        """
         * func PutAuthEx(expires, callbackUrl) => PutAuthRet
         * 上传授权（生成一个短期有效的可匿名上传URL）
        """
        url = config.IO_HOST + '/put-auth/' + str(expires) + '/callback/' + urlsafe_b64encode(cbUrl)
        return self.Conn.Call(url)

    def Get(self, key, attName):
        """
         * func Get(key string, attName string) => GetRet
         * 下载授权（生成一个短期有效的可匿名下载URL）
        """
        entryURI = self.BucketName + ':' + key
        url = config.RS_HOST + '/get/' + urlsafe_b64encode(entryURI) + '/attName/' + urlsafe_b64encode(attName)
        return self.Conn.Call(url)

    def GetIfNotModified(self, key, attName, base):
        """
         * func GetIfNotModified(key string, attName string, base string) => GetRet
         * 下载授权（生成一个短期有效的可匿名下载URL），如果服务端文件没被人修改的话（用于断点续传）
        """
        entryURI = self.BucketName + ':' + key
        url = config.RS_HOST + '/get/' + urlsafe_b64encode(entryURI) + '/attName/' + urlsafe_b64encode(attName) + '/base/' + base
        return self.Conn.Call(url)

    def Stat(self, key):
        """
         * func Stat(key string) => Entry
         * 查看资源属性
        """
        entryURI = self.BucketName + ':' + key
        url = config.RS_HOST + '/stat/' + urlsafe_b64encode(entryURI)
        return self.Conn.Call(url)

    def Publish(self, domain):
        """
         * func Publish(domain string) => Bool
         * 将本 Table 的内容作为静态资源发布。静态资源的url为：http://domain/key
        """
        url = config.RS_HOST + '/publish/' + urlsafe_b64encode(domain) + '/from/' + self.BucketName
        return self.Conn.CallNoRet(url)

    def Unpublish(self, domain):
        """
         * func Unpublish(domain string) => Bool
         * 取消发布
        """
        url = config.RS_HOST + '/unpublish/' + urlsafe_b64encode(domain)
        return self.Conn.CallNoRet(url)

    def Delete(self, key):
        """
         * func Delete(key string) => Bool
         * 删除资源
        """
        entryURI = self.BucketName + ':' + key
        url = config.RS_HOST + '/delete/' + urlsafe_b64encode(entryURI)
        return self.Conn.CallNoRet(url)

    def Mkbucket(self, bucketname):
        """
         * func Mkbucket(bucketname string) => Bool
         * 创建一个资源表
        """
        url = config.RS_HOST + '/mkbucket/' + bucketname
        return self.Conn.Call(url)

    def Buckets(self):
        """
         * func Buckets() => list
         * 列出所有资源表
        """
        url = config.RS_HOST + '/buckets'
        return self.Conn.Call(url)

    def Drop(self, bucketname):
        """
         * func Drop(bucketname string) => Bool
         * 删除一个资源表（慎用！）
        """
        url = config.RS_HOST + '/drop/' + bucketname
        return self.Conn.CallNoRet(url)

    def SetProtected(self, protectedMode):
        """
         * func SetProtected(protectedMode string) => Bool
         * 对 Bucket 设置保护，使资源本身不能被直接访问（只能访问被授权的经处理过的资源，比如打水印的图片)
        """
        url = config.PUB_HOST + '/accessMode/' + self.BucketName + '/mode/' + str(protectedMode)
        return self.Conn.Call(url)

    def SetSeparator(self, sep):
        """
         * func SetSeparator(sep string) => Bool
         * 设置分隔符
        """
        url = config.PUB_HOST + '/separator/' + self.BucketName + '/sep/' + urlsafe_b64encode(sep)
        return self.Conn.Call(url)

    def SetStyle(self, name, style):
        """
         * func SetStyle(name string, style string) => Bool
         * 设置缩略图规格别名
        """
        url = config.PUB_HOST + '/style/' + self.BucketName + '/name/' + urlsafe_b64encode(name) + '/style/' + urlsafe_b64encode(style)
        return self.Conn.Call(url)

    def UnsetStyle(self, name):
        """
         * func UnsetStyle(name string) => Bool
         * 删除指定缩略图规格
        """
        url = config.PUB_HOST + '/unstyle/' + self.BucketName + '/name/' + urlsafe_b64encode(name)
        return self.Conn.Call(url)

    def SaveAs(self, key, source_url, opWithParams):
        """
         * func SaveAs(target_key, source_url, opWithParams string) => Bool
         * 调用相关接口进行云处理并持久化存储处理结构
        """
        entryURI = self.BucketName + ":" + key
        saveAsEntryURI = urlsafe_b64encode(entryURI)
        saveAsParam = "/save-as/" + saveAsEntryURI
        newurl = source_url + "?" + opWithParams + saveAsParam
        return self.Conn.Call(newurl)

    def ImageMogrifyAs(self, key, source_img_url, opts):
        """
         * func ImageMogrifyAs(target_key string, source_img_url string, opts map) => Bool
         * 基于指定URL的原图生成缩略图并以指定的key持久化存储该缩略图
        """
        mogrifyParams = fileop.mkImageMogrifyParams(opts)
        return self.SaveAs(key, source_img_url, mogrifyParams)

