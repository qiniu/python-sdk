# -*- coding: utf-8 -*-
from .util import shell_quote


class Git(object):
    def __init__(self, commands):
        self.commands = commands

    def _run_git(self, repo_path, args, **opts):
        if repo_path:
            opts['cwd'] = repo_path
        return self.commands.run('git {0}'.format(' '.join(args)), **opts)

    def clone(self, repo_url, path=None, branch=None, depth=None, **opts):
        args = ['clone']
        if depth:
            args.extend(['--depth', shell_quote(depth)])
        if branch:
            args.extend(['--branch', shell_quote(branch)])
        args.append(shell_quote(repo_url))
        if path:
            args.append(shell_quote(path))
        return self._run_git(None, args, **opts)

    def init(self, repo_path, bare=False, initial_branch=None, **opts):
        args = ['init']
        if bare:
            args.append('--bare')
        if initial_branch:
            args.extend(['--initial-branch', shell_quote(initial_branch)])
        return self._run_git(repo_path, args, **opts)

    def status(self, repo_path, **opts):
        return self._run_git(
            repo_path, [
                'status', '--porcelain=v1', '-b'], **opts)

    def add(self, repo_path, files=None, all=False, **opts):
        args = ['add']
        if all:
            args.append('--all')
        else:
            for path in files or ['.']:
                args.append(shell_quote(path))
        return self._run_git(repo_path, args, **opts)

    def commit(self, repo_path, message, allow_empty=False, **opts):
        args = ['commit', '-m', shell_quote(message)]
        if allow_empty:
            args.append('--allow-empty')
        return self._run_git(repo_path, args, **opts)

    def configure_user(self, repo_path, name, email, **opts):
        name_result = self._run_git(
            repo_path,
            ['config', 'user.name', shell_quote(name)],
            **opts
        )
        if name_result.exit_code != 0:
            return name_result
        return self._run_git(
            repo_path,
            ['config', 'user.email', shell_quote(email)],
            **opts
        )

    configureUser = configure_user

    def pull(self, repo_path, remote=None, branch=None, **opts):
        args = ['pull']
        if remote:
            args.append(shell_quote(remote))
        if branch:
            args.append(shell_quote(branch))
        return self._run_git(repo_path, args, **opts)

    def push(self, repo_path, remote=None, branch=None, **opts):
        args = ['push']
        if remote:
            args.append(shell_quote(remote))
        if branch:
            args.append(shell_quote(branch))
        return self._run_git(repo_path, args, **opts)
