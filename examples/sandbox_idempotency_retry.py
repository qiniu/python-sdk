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

idempotency_key = 'sdk-example-{}'.format(int(time.time()))
print('幂等键: {}'.format(idempotency_key))

first_sandbox = Sandbox.create(
    template='base', timeout=300, endpoint=ENDPOINT, api_key=API_KEY,
    idempotency_key=idempotency_key,
)
second_sandbox = None
try:
    print('第一次创建: {}'.format(first_sandbox.sandbox_id))
    second_sandbox = Sandbox.create(
        template='base', timeout=300, endpoint=ENDPOINT, api_key=API_KEY,
        idempotency_key=idempotency_key,
    )
    print('第二次创建: {}'.format(second_sandbox.sandbox_id))
    if first_sandbox.sandbox_id != second_sandbox.sandbox_id:
        raise RuntimeError(
            '幂等重试验证失败：两次创建返回不同沙箱: {} vs {}'.format(
                first_sandbox.sandbox_id, second_sandbox.sandbox_id))
    print('幂等重试验证通过：两次创建返回同一沙箱')
finally:
    if second_sandbox is not None and second_sandbox.sandbox_id != first_sandbox.sandbox_id:
        second_sandbox.kill()
    first_sandbox.kill()
    print('沙箱已清理')
