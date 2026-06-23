# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(timeout=300)
    try:
        print('created:', sandbox.sandbox_id)
        sandbox.set_timeout(600)
        sandbox.refresh(duration=600)
        info = sandbox.get_info()
        print('state:', info.get('state'))
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
