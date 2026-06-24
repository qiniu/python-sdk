# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import time

from qiniu.services.sandbox import CommandExitError

from sandbox_common import cleanup_sandbox, create_sandbox, run_example

try:
    from urllib.parse import quote, urlparse, urlunparse
except ImportError:
    from urllib import quote
    from urlparse import urlparse, urlunparse


def is_git_ok(result):
    message = result.stderr or result.stdout or result.error or ''
    return result.exit_code == 0 or (
        result.exit_code == -1 and
        not result.error and
        'fatal:' not in message.lower() and
        'error:' not in message.lower()
    )


def assert_git_ok(step, result):
    message = result.stderr or result.stdout or result.error or ''
    if not is_git_ok(result):
        raise RuntimeError(
            '{0} failed with exit {1}: {2}'.format(
                step,
                result.exit_code,
                message,
            )
        )
    print(step + ':', result.exit_code)
    return result


def is_retryable_git_network_error(result):
    message = (result.stderr or result.stdout or result.error or '').lower()
    return result.exit_code != 0 and (
        'gnutls' in message or
        'tls connection' in message or
        'unable to access' in message or
        'the remote end hung up unexpectedly' in message
    )


def assert_git_network_ok(step, run, attempts=5):
    result = None
    for attempt in range(attempts):
        result = run()
        if result.exit_code == 0:
            print(step + ':', result.exit_code)
            return result
        if (
                not is_retryable_git_network_error(result) or
                attempt == attempts - 1):
            return assert_git_ok(step, result)
        print('{0}: retry {1}/{2}'.format(step, attempt + 2, attempts))
        time.sleep(attempt + 1)


def remote_git_config():
    repo_url = os.getenv('GIT_REPO_URL')
    username = os.getenv('GIT_USERNAME')
    password = os.getenv('GIT_PASSWORD') or os.getenv('GITHUB_TOKEN')
    if password and not username:
        username = 'x-access-token'
    if not repo_url or not username or not password:
        return None
    return repo_url, username, password


def credentialed_repo_url(repo_url, username, password):
    parsed = urlparse(repo_url)
    if parsed.scheme not in ('http', 'https'):
        raise RuntimeError(
            'remote git push: only http(s) URLs support credentials')
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


def clone_remote_with_credentials(sandbox, repo_url, repo_path,
                                  username, password, attempts=5):
    auth_url = credentialed_repo_url(repo_url, username, password)
    result = None
    for attempt in range(attempts):
        sandbox.commands.run('rm -rf {0}'.format(repo_path))
        result = sandbox.git.clone(
            auth_url,
            repo_path,
            depth=1,
            timeout=180,
            request_timeout=180,
        )
        if is_git_ok(result):
            print('git clone remote:', result.exit_code)
            return result
        if (
                not is_retryable_git_network_error(result) or
                attempt == attempts - 1):
            raise RuntimeError(
                'git clone remote failed with exit {0}'.format(
                    result.exit_code,
                )
            )
        print('git clone remote: retry {0}/{1}'.format(
            attempt + 2,
            attempts,
        ))
        time.sleep(attempt + 1)


def run_remote_push_demo(sandbox):
    config = remote_git_config()
    if not config:
        print('remote git push: skipped, GIT_REPO_URL/Git credentials missing')
        return

    repo_url, username, password = config
    branch = 'python-sdk-example-{0}'.format(int(time.time() * 1000))
    repo_path = '/tmp/qiniu-python-sdk-git/remote'

    assert_git_ok(
        'git http version',
        sandbox.git.set_config(
            None, 'http.version', 'HTTP/1.1', global_config=True),
    )

    try:
        clone_remote_with_credentials(
            sandbox,
            repo_url,
            repo_path,
            username,
            password,
        )
    except Exception as err:
        print('remote git push skipped:', err)
        return
    assert_git_ok(
        'reset remote url',
        sandbox.git.remote_add(repo_path, 'origin', repo_url, overwrite=True),
    )
    assert_git_ok(
        'configure remote user',
        sandbox.git.configure_user(
            repo_path,
            'Qiniu Python SDK',
            'qiniu-python-sdk@example.com',
        ),
    )
    assert_git_ok(
        'checkout remote branch',
        sandbox.git.checkout_branch(repo_path, branch, create=True),
    )
    sandbox.files.write(
        repo_path + '/python-sdk-example.txt',
        'qiniu-python-sdk example push {0}\n'.format(branch),
    )
    assert_git_ok('git add remote', sandbox.git.add(repo_path, all=True))
    assert_git_ok(
        'git commit remote',
        sandbox.git.commit(repo_path, 'test: qiniu python sdk example push'),
    )
    assert_git_network_ok(
        'git push remote',
        lambda: sandbox.git.push(
            repo_path,
            'origin',
            'HEAD:refs/heads/{0}'.format(branch),
            username=username,
            password=password,
            timeout=180,
            request_timeout=180,
        ),
    )
    print('remote git branch:', branch)


def main():
    repo_path = '/tmp/qiniu-python-sdk-git/repo'
    clone_path = '/tmp/qiniu-python-sdk-git/clone'
    sandbox = create_sandbox(timeout=300)
    try:
        sandbox.commands.run(
            'mkdir -p /tmp/qiniu-python-sdk-git/repo'
        )
        assert_git_ok(
            'git init',
            sandbox.git.init(repo_path, initial_branch='main'),
        )
        assert_git_ok(
            'configure user',
            sandbox.git.configure_user(
                repo_path,
                'Sandbox Demo',
                'sandbox-demo@example.com',
            ),
        )
        sandbox.files.write(repo_path + '/README.md', '# sandbox git demo\n')
        assert_git_ok('git add', sandbox.git.add(repo_path, all=True))
        assert_git_ok(
            'git commit',
            sandbox.git.commit(repo_path, 'feat: initial commit'),
        )
        assert_git_ok('git clone', sandbox.git.clone(repo_path, clone_path))
        try:
            status = sandbox.git.status(clone_path)
            print('clone status clean:', status.is_clean)
        except CommandExitError as err:
            print('git status skipped:', err)
        run_remote_push_demo(sandbox)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
