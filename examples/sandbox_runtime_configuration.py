# -*- coding: utf-8 -*-
from __future__ import print_function

import os

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def main():
    sandbox = create_sandbox(timeout=300)
    try:
        listed = sandbox.client.list_sandboxes_v2(
            template=[sandbox.template_id],
        )
        print('sandboxes using template:', listed)

        print('current injections:', sandbox.get_injections())
        sandbox.update_injections([{
            'type': 'http',
            'base_url': 'https://api.example.com/v1/*',
            'headers': {'X-From-Sandbox': 'qiniu-python-sdk'},
        }])
        print('updated injections:', sandbox.get_injections())

        github_token = os.getenv('QINIU_SANDBOX_GITHUB_TOKEN')
        if github_token:
            sandbox.update_github_token(github_token)
            print('updated GitHub token')
        else:
            print('GitHub token update skipped: '
                  'QINIU_SANDBOX_GITHUB_TOKEN is not set')
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
