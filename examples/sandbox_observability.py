# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import SandboxError

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def print_optional(label, fn):
    try:
        value = fn()
        if label == 'logs' and isinstance(value, dict):
            print(label + ':', len(value.get('logs') or []))
        else:
            print(label + ':', value)
    except SandboxError as err:
        print(label + ' skipped:', err)


def main():
    sandbox = create_sandbox(metadata={'example': 'sandbox_observability'})
    try:
        sandbox.wait_for_ready(timeout=60)
        print('running:', sandbox.is_running(request_timeout=3))
        print('envd url:', sandbox.envd_url())
        print('envd host:', sandbox.get_host(49983))
        print('mcp url:', sandbox.get_mcp_url())
        print('mcp token present:', bool(sandbox.get_mcp_token()))
        print('download url present:', bool(sandbox.download_url('/tmp/demo.txt')))
        print('upload url present:', bool(sandbox.upload_url('/tmp/demo.txt')))
        print_optional('metrics', lambda: sandbox.get_metrics())
        print_optional('logs', lambda: sandbox.get_logs())
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
