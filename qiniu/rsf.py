# -*- coding: utf-8 -*-
import auth.digest
import conf
import urllib

EOF = 'EOF'


class Client(object):
    conn = None

    def __init__(self, mac=None):
        if mac is None:
            mac = auth.digest.Mac()
        self.conn = auth.digest.Client(host=conf.RSF_HOST, mac=mac)

    def list_prefix(self, bucket, prefix=None, marker=None, limit=None):
        '''前缀查询:
         * bucket => str
         * prefix => str
         * marker => str
         * limit => int
         * return ret => {'items': items, 'marker': markerOut}, err => str

        1. 首次请求 marker = None
        2. 无论 err 值如何，均应该先看 ret.get('items') 是否有内容
        3. 如果后续没有更多数据，err 返回 EOF，markerOut 返回 None（但不通过该特征来判断是否结束）
        '''
        ops = {
            'bucket': bucket,
        }
        if marker is not None:
            ops['marker'] = marker
        if limit is not None:
            ops['limit'] = limit
        if prefix is not None:
            ops['prefix'] = prefix
        url = '%s?%s' % ('/list', urllib.urlencode(ops))
        ret, err, code = self.conn.call_with(
            url, body=None, content_type='application/x-www-form-urlencoded')
        if ret and not ret.get('marker'):
            err = EOF
        return ret, err
