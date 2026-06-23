# -*- coding: utf-8 -*-
from __future__ import print_function
import time

from qiniu.services.sandbox import PtySize, SandboxError

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(metadata={'example': 'sandbox_runtime'})
    watcher = None
    try:
        stdout = []
        result = sandbox.commands.run(
            'printf runtime',
            on_stdout=stdout.append,
        )
        print('command stdout:', result.stdout)
        print('callback stdout:', ''.join(stdout))

        sandbox.files.write_files([
            {'path': '/tmp/qiniu-runtime-a.txt', 'data': 'a'},
            {'path': '/tmp/qiniu-runtime-b.txt', 'data': 'b'},
        ])
        print('write_files: ok')

        try:
            watcher = sandbox.files.watch_dir('/tmp')
            sandbox.files.write('/tmp/qiniu-runtime-watch.txt', 'watch')
            time.sleep(1)
            for event in watcher.get_new_events():
                print('watch event:', event.name, event.type)
        except Exception as err:
            print('watch_dir skipped:', err)
        finally:
            if watcher is not None:
                try:
                    watcher.stop()
                except SandboxError as err:
                    print('failed to stop watcher:', err)

        try:
            pty = sandbox.pty.create(PtySize(rows=24, cols=80), timeout=30)
            print('pty pid:', pty.pid)
            sandbox.pty.send_stdin(pty.pid, 'echo pty-ready\n')
            sandbox.pty.send_stdin(pty.pid, 'exit\n')
            pty_result = pty.wait()
            print('pty stdout:', pty_result.stdout)
        except SandboxError as err:
            print('pty skipped:', err)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
