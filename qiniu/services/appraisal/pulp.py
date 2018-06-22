import json
from qiniu.http import _post_with_qiniu_mac
from qiniu.auth import QiniuMacAuth


class AppraisalOperation(object):
    '''视频审核的动作（鉴黄，鉴恐， 鉴政治人物)'''
    ops = ("pulp", "terror", "politician")

    def __init__(self, op, hook_url="", params=None):
        if op not in self.ops:
            raise ValueError("op must be in %s" % self.ops)
        if params is not None and not isinstance(params, dict):
            raise TypeError("params must be dict: %s" % params)
        self.op = op
        self.hook_url = hook_url
        self.params = params

    def __str__(self):
        return 'op: %s\nhook_url: %s\nparams: %s\n' % (self.op, self.hook_url, self.params)


def video_appraisal(auth, vid, url, ops, params=None):
    """
    @vid 视频唯一的ID
    @url 视频鉴黄的地址
    @params 字典，视频处理的参数
    @ops 视频检测命令 [AppraisalOperation...]
    具体参数格式参考:
    https://developer.qiniu.com/dora/manual/4258/video-pulp'''
    """
    if params is not None:
        if not isinstance(params, dict):
            raise TypeError("params must be instance of dict, invalid params: %s" % params)
    if not isinstance(ops, list):
        raise TypeError("ops must be instance of list, invalid ops: %s" % ops)
    if len(ops) <= 0:
        raise ValueError("length of ops must greater than zero")
    if not isinstance(auth, QiniuMacAuth):
        raise TypeError("auth must be instance of QiniuMacAuth")

    def getop(operation):
        d = {
            "op": operation.op,
        }
        if operation.hook_url:
            d["hookURL"] = operation.hook_url
        if operation.params:
            d["params"] = operation.params
        return d

    ops = [getop(op) for op in ops]

    if params:
        data = {
            "data": {
                "uri": url,
            },
            "params": params
        }
    else:
        data = {
            "data": {
                "uri": url,
            },
        }
    data['ops'] = ops

    return _post_with_qiniu_mac("http://argus.atlab.ai/v1/video/%s" % vid, data, auth)


def video_pulp(auth, vid, url, op=None, params=None):
    if op is None:
        op = AppraisalOperation("pulp")
    else:
        if not isinstance(op, AppraisalOperation):
            raise TypeError("op must be instance of AppraisalOperation: %s" % op)
        if op.op != "pulp":
            raise ValueError("pulp appraisal operation must be pulp: %s" % op.op)
    return video_appraisal(auth, vid, url, [op], params)

def video_terror(auth, vid, url, op=None, params=None):
    if op is None:
        op = AppraisalOperation("terror")
    else:
        if not isinstance(op, AppraisalOperation):
            raise TypeError("op must be instance of AppraisalOperation: %s" % op)
        if op.op != "politician":
            raise ValueError("terror appraisal operation must be terror: %s" % op.op)
    return video_appraisal(auth, vid, url, [op], params)

def video_politician(auth, vid, url, op=None, params=None):
    if op is None:
        op = AppraisalOperation("politician")
    else:
        if not isinstance(op, AppraisalOperation):
            raise TypeError("op must be instance of AppraisalOperation: %s" % op)
        if op.op != "politician":
            raise ValueError("politician appraisal operation must be politician: %s" % op.op)
    return video_appraisal(auth, vid, url, [op], params)
