# -*- coding: utf-8 -*-
from __future__ import print_function

from io import BytesIO

from qiniu.services.sandbox import SandboxError

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(metadata={'example': 'sandbox_filesystem'})
    base = '/tmp/qiniu-python-sdk-files'
    renamed_path = base + '/renamed.txt'
    try:
        sandbox.files.make_dir(base)
        print('exists base:', sandbox.files.exists(base))

        text_info = sandbox.files.write(base + '/hello.txt', 'hello')
        print('write text:', text_info.path if text_info else 'ok')
        print('read text:', sandbox.files.read_text(base + '/hello.txt'))

        try:
            sandbox.files.write(
                base + '/bytes.bin',
                BytesIO(b'\x00qiniu\xff'),
                use_octet_stream=True,
            )
        except SandboxError as err:
            print('octet-stream write skipped:', err)
            sandbox.files.write(base + '/bytes.bin', BytesIO(b'\x00qiniu\xff'))
        print('read bytes:', list(sandbox.files.read(
            base + '/bytes.bin',
            format='bytes',
        )))

        sandbox.files.write_files([
            {'path': base + '/a.txt', 'data': 'a'},
            {'path': base + '/b.txt', 'data': 'b'},
        ])
        print('list:', [entry.name for entry in sandbox.files.list(base)])

        info = sandbox.files.get_info(base + '/hello.txt')
        print('stat:', info.name, info.type, info.size)

        chunks = sandbox.files.read(
            base + '/hello.txt',
            format='stream',
            chunk_size=2,
        )
        print('stream:', b''.join(chunks).decode('utf-8'))

        moved = sandbox.files.rename(base + '/hello.txt', renamed_path)
        print('renamed:', moved.path)
        sandbox.files.remove(renamed_path)
        print('exists renamed:', sandbox.files.exists(renamed_path))
    finally:
        try:
            sandbox.files.remove(base)
        except Exception:
            pass
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
