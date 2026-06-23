# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(
        metadata={'example': 'sandbox_create'},
        envs={'HELLO': 'qiniu'},
    )
    try:
        print('sandbox:', sandbox.sandbox_id)
        result = sandbox.commands.run('printf "$HELLO"')
        print('stdout:', result.stdout)

        sandbox.files.write('/tmp/qiniu.txt', 'hello from qiniu sandbox')
        print('file:', sandbox.files.read_text('/tmp/qiniu.txt'))
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
