# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import SandboxError

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(metadata={'example': 'sandbox_commands'})
    try:
        stdout = []
        result = sandbox.commands.run(
            'printf command-callback',
            on_stdout=stdout.append,
        )
        print('run:', result.stdout)
        print('callback:', ''.join(stdout))

        handle = sandbox.commands.start(
            'read line; echo "stdin:$line"',
            stdin=True,
            tag='qiniu-python-sdk-commands',
            timeout=30,
        )
        print('started pid:', handle.pid)
        print('processes:', [
            item.pid for item in sandbox.commands.list()
            if item.pid == handle.pid or item.tag == 'qiniu-python-sdk-commands'
        ])
        try:
            sandbox.commands.send_stdin(handle.pid, 'hello\n')
            sandbox.commands.close_stdin(handle.pid)
            print('stdin result:', handle.wait().stdout.strip())
        except SandboxError as err:
            print('stdin skipped:', err)
            try:
                sandbox.commands.kill(handle.pid)
            except SandboxError:
                pass

        sleeper = sandbox.commands.run(
            'sleep 30',
            background=True,
            tag='qiniu-python-sdk-kill',
        )
        print('background pid:', sleeper.pid)
        try:
            connected = sandbox.commands.connect(sleeper.pid)
            print('connect running pid:', connected.pid)
        except SandboxError as err:
            print('connect running process skipped:', err)
        try:
            print('kill background:', sandbox.commands.kill(sleeper.pid))
        except SandboxError as err:
            print('kill background skipped:', err)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
