# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import cleanup_sandbox, create_sandbox, run_example


def assert_git_ok(step, result):
    if result.exit_code != 0:
        raise RuntimeError(
            '{0} failed with exit {1}: {2}'.format(
                step,
                result.exit_code,
                result.stderr or result.stdout,
            )
        )
    print(step + ':', result.exit_code)
    return result


def main():
    repo_path = '/tmp/qiniu-python-sdk-git/repo'
    clone_path = '/tmp/qiniu-python-sdk-git/clone'
    sandbox = create_sandbox(timeout=300)
    try:
        sandbox.commands.run(
            'mkdir -p /tmp/qiniu-python-sdk-git/repo'
        )
        assert_git_ok('git init', sandbox.git.init(repo_path))
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
        print(sandbox.git.status(clone_path).stdout)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
