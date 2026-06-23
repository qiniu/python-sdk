# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import (
    GitRepositoryResource,
    KodoResource,
    SandboxError,
)
from qiniu.services.sandbox.util import shell_quote
from sandbox_common import (
    cleanup_sandbox,
    create_sandbox,
    env,
    run_example,
)


def is_optional_resource_error(err):
    status_code = getattr(err, 'status_code', None)
    if status_code in (404, 408, 409, 429, 500, 502, 503, 504):
        return True
    message = str(err).lower()
    return (
        'timeout' in message or
        'timed out' in message or
        'not found' in message or
        'temporarily unavailable' in message
    )


def run_git_resource_example():
    repo_url = env('GIT_REPO_URL')
    repo_token = env('GITHUB_TOKEN')
    if not repo_url or not repo_token:
        print(
            'Skip GitHub repository resource: '
            'set GIT_REPO_URL and GITHUB_TOKEN.'
        )
        return

    mount_path = env('QINIU_SANDBOX_GIT_MOUNT_PATH', '/workspace/repo')
    try:
        sandbox = create_sandbox(
            timeout=300,
            metadata={'example': 'sandbox_resources_git'},
            resources=[
                GitRepositoryResource(
                    url=repo_url,
                    mount_path=mount_path,
                    authorization_token=repo_token,
                )
            ],
        )
    except SandboxError as err:
        if is_optional_resource_error(err):
            print('Skip GitHub repository resource:', err)
            return
        raise
    try:
        print('Git resource sandbox:', sandbox.sandbox_id)
        print(sandbox.commands.run('ls -la {0} | head -20'.format(
            shell_quote(mount_path)
        )).stdout)
    finally:
        cleanup_sandbox(sandbox)


def run_kodo_resource_example():
    bucket = env('QINIU_SANDBOX_KODO_BUCKET')
    if not bucket:
        print('Skip Kodo resource: set QINIU_SANDBOX_KODO_BUCKET.')
        return

    mount_path = env('QINIU_SANDBOX_KODO_MOUNT_PATH', '/mnt/kodo')
    resource = KodoResource(
        bucket=bucket,
        mount_path=mount_path,
        prefix=env('QINIU_SANDBOX_KODO_PREFIX') or None,
    )
    try:
        sandbox = create_sandbox(
            timeout=300,
            metadata={'example': 'sandbox_resources_kodo'},
            resources=[resource],
        )
    except SandboxError as err:
        if is_optional_resource_error(err):
            print('Skip Kodo resource:', err)
            return
        raise
    try:
        print('Kodo resource sandbox:', sandbox.sandbox_id)
        print(sandbox.commands.run('ls -la {0} | head -20'.format(
            shell_quote(mount_path)
        )).stdout)
        test_path = mount_path + '/qiniu-python-sdk-resource-test.txt'
        result = sandbox.commands.run(
            'sh -c {0}'.format(shell_quote(
                'echo qiniu-python-sdk > {0} && cat {0}'.format(
                    shell_quote(test_path)
                )
            ))
        )
        if result.exit_code != 0:
            raise RuntimeError(result.stderr or result.stdout)
        print('Kodo write/read:', result.stdout.strip())
    finally:
        cleanup_sandbox(sandbox)


def main():
    run_git_resource_example()
    run_kodo_resource_example()


if __name__ == '__main__':
    run_example(main)
