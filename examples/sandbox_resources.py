# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import GitRepositoryResource, KodoResource
from sandbox_common import (
    cleanup_sandbox,
    create_sandbox,
    env,
    run_example,
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
    try:
        print('Git resource sandbox:', sandbox.sandbox_id)
        print(sandbox.commands.run('ls -la {0} | head -20'.format(
            mount_path
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
    sandbox = create_sandbox(
        timeout=300,
        metadata={'example': 'sandbox_resources_kodo'},
        resources=[resource],
    )
    try:
        print('Kodo resource sandbox:', sandbox.sandbox_id)
        print(sandbox.commands.run('ls -la {0} | head -20'.format(
            mount_path
        )).stdout)
        test_path = mount_path + '/qiniu-python-sdk-resource-test.txt'
        result = sandbox.commands.run(
            'sh -c "echo qiniu-python-sdk > {0} && cat {0}"'.format(test_path)
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
