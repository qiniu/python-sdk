# -*- coding: utf-8 -*-
from __future__ import print_function

import time

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

try:
    from urllib.parse import quote, urlparse, urlunparse
except ImportError:
    from urllib import quote
    from urlparse import urlparse, urlunparse


def git_ok(result):
    message = result.stderr or result.stdout or result.error or ''
    return result.exit_code == 0 or (
        result.exit_code == -1 and
        not result.error and
        'fatal:' not in message.lower() and
        'error:' not in message.lower()
    )


def assert_git_ok(step, result):
    if not git_ok(result):
        raise RuntimeError(
            '{0} failed with exit {1}: {2}'.format(
                step,
                result.exit_code,
                result.stderr or result.stdout or result.error,
            )
        )
    print(step + ':', result.exit_code)
    return result


def credentialed_repo_url(repo_url, username, password):
    parsed = urlparse(repo_url)
    if parsed.scheme not in ('http', 'https'):
        raise RuntimeError(
            'GitHub repository resource push requires an http(s) URL')
    netloc = parsed.netloc.split('@', 1)[-1]
    auth = '{0}:{1}@'.format(
        quote(username, safe=''),
        quote(password, safe=''),
    )
    return urlunparse((
        parsed.scheme,
        auth + netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))


def push_branch_with_credentials(sandbox, repo_path, repo_url, branch,
                                 username, password):
    auth_url = credentialed_repo_url(repo_url, username, password)
    command = (
        'cd {repo_path} && '
        'git push {auth_url} HEAD:refs/heads/{branch} && '
        'git ls-remote --heads {auth_url} {branch}'
    ).format(
        repo_path=shell_quote(repo_path),
        auth_url=shell_quote(auth_url),
        branch=shell_quote(branch),
    )
    result = sandbox.commands.run(
        command,
        timeout=180,
        request_timeout=180,
    )
    if branch not in (result.stdout or ''):
        raise RuntimeError(
            'git resource push verification failed with exit {0}'.format(
                result.exit_code,
            )
        )
    print('git resource push:', result.exit_code)
    return result


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
    repo_username = env('GIT_USERNAME') or 'x-access-token'
    repo_password = env('GIT_PASSWORD') or repo_token
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
        branch = 'python-sdk-example-{0}'.format(int(time.time() * 1000))
        assert_git_ok(
            'git resource http version',
            sandbox.git.set_config(
                None, 'http.version', 'HTTP/1.1', global_config=True),
        )
        assert_git_ok(
            'git resource configure user',
            sandbox.git.configure_user(
                mount_path,
                'Qiniu Python SDK',
                'qiniu-python-sdk@example.com',
            ),
        )
        assert_git_ok(
            'git resource checkout branch',
            sandbox.git.checkout_branch(mount_path, branch, create=True),
        )
        sandbox.files.write(
            mount_path + '/python-sdk-resource-example.txt',
            'qiniu-python-sdk resource push {0}\n'.format(branch),
        )
        assert_git_ok(
            'git resource add',
            sandbox.git.add(mount_path, all=True),
        )
        assert_git_ok(
            'git resource commit',
            sandbox.git.commit(
                mount_path,
                'test: qiniu python sdk resource example push',
            ),
        )
        push_branch_with_credentials(
            sandbox,
            mount_path,
            repo_url,
            branch,
            repo_username,
            repo_password,
        )
        print('git resource branch:', branch)
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
        if (
                result.exit_code != 0 and
                'qiniu-python-sdk' not in (result.stdout or '')):
            raise RuntimeError(result.stderr or result.stdout)
        print('Kodo write/read:', result.stdout.strip())
        sandbox.commands.run('rm -f {0}'.format(shell_quote(test_path)))
    finally:
        cleanup_sandbox(sandbox)

    read_only = KodoResource(
        bucket=bucket,
        mount_path=mount_path,
        prefix=env('QINIU_SANDBOX_KODO_PREFIX') or None,
        read_only=True,
    )
    try:
        sandbox = create_sandbox(
            timeout=300,
            metadata={'example': 'sandbox_resources_kodo_read_only'},
            resources=[read_only],
        )
    except SandboxError as err:
        if is_optional_resource_error(err):
            print('Skip read-only Kodo resource:', err)
            return
        raise
    try:
        print('Read-only Kodo resource sandbox:', sandbox.sandbox_id)
        print(sandbox.commands.run('ls -la {0} | head -20'.format(
            shell_quote(mount_path)
        )).stdout)
    finally:
        cleanup_sandbox(sandbox)


def main():
    run_git_resource_example()
    run_kodo_resource_example()


if __name__ == '__main__':
    run_example(main)
