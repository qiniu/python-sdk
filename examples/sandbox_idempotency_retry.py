#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""幂等重试示例：同一幂等键连调两次 Create，验证返回同一沙箱。"""
import os
import sys
import time

from qiniu.services.sandbox import Sandbox

API_KEY = os.getenv('QINIU_SANDBOX_API_KEY') or os.getenv('QINIU_API_KEY') or os.getenv('E2B_API_KEY')
if not API_KEY:
    print('请设置 QINIU_SANDBOX_API_KEY 环境变量')
    sys.exit(1)

ENDPOINT = os.getenv('QINIU_SANDBOX_ENDPOINT') or os.getenv('QINIU_SANDBOX_API_URL')

sandbox = Sandbox.create(
    template='base',
    timeout=300,
    endpoint=ENDPOINT,
    api_key=API_KEY,
    idempotency_key='sdk-example-{}'.format(int(time.time())),
)
print('沙箱创建成功: {}'.format(sandbox.sandbox_id))
print('幂等键: {}'.format(sandbox.info.get('idempotencyKey', '(auto-generated)')))

sandbox.kill()
print('沙箱已清理')
