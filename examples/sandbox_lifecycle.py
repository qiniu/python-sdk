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
    sandbox = create_sandbox(timeout=300)
    try:
        print('created:', sandbox.sandbox_id)
        sandbox.set_timeout(600)
        sandbox.refresh(duration=600)
        info = sandbox.get_info()
        print('state:', info.get('state'))
        print_optional('metrics', sandbox.get_metrics)
        print_optional('logs', sandbox.get_logs)
        sandbox.pause()
        print('paused:', sandbox.sandbox_id)
        sandbox.resume(timeout=300)
        print('resumed:', sandbox.sandbox_id)
        try:
            print('network:', sandbox.update_network({'allowInternet': True}))
        except Exception as err:
            print('update network skipped:', err)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
