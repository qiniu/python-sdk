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
    sandbox = create_sandbox(
        timeout=300, auto_pause=True, auto_pause_memory=True,
        auto_resume={'enabled': True}, network={'allowPublicTraffic': True})
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
        # Disk-only pause loses running processes; explicitly connect to restart.
        sandbox.pause(memory=False)
        sandbox.connect()  # v2: extend TTL to at least 300s, never shorten it.
        print('cold-booted:', sandbox.sandbox_id)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
