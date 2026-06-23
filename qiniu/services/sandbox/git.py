# -*- coding: utf-8 -*-
import uuid

from qiniu.compat import basestring

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from .errors import (
    CommandExitError,
    GitAuthException,
    GitUpstreamException,
    InvalidArgumentException,
    SandboxError,
)
from .util import shell_quote


def _normalize_paths(paths):
    if paths is None:
        return None
    if isinstance(paths, basestring):
        return [paths]
    return paths


RESET_MODES = set(['soft', 'mixed', 'hard', 'merge', 'keep'])


def _remove_credential_file(filesystem, path):
    if not path:
        return
    try:
        filesystem.remove(path)
    except Exception:
        pass


def _cleanup_after_wait(wait, filesystem, path):
    def wrapped_wait(*args, **kwargs):
        try:
            return wait(*args, **kwargs)
        finally:
            _remove_credential_file(filesystem, path)
    return wrapped_wait


class GitFileStatus(object):
    def __init__(self, name, status, index_status, working_tree_status,
                 staged, renamed_from=None):
        self.name = name
        self.status = status
        self.index_status = index_status
        self.working_tree_status = working_tree_status
        self.staged = staged
        self.renamed_from = renamed_from


class GitStatus(object):
    def __init__(self, current_branch=None, upstream=None, ahead=0, behind=0,
                 detached=False, file_status=None):
        self.current_branch = current_branch
        self.upstream = upstream
        self.ahead = ahead
        self.behind = behind
        self.detached = detached
        self.file_status = file_status or []

    @property
    def is_clean(self):
        return len(self.file_status) == 0

    @property
    def has_changes(self):
        return len(self.file_status) > 0

    @property
    def has_staged(self):
        return any(item.staged for item in self.file_status)

    @property
    def has_untracked(self):
        return any(item.status == 'untracked' for item in self.file_status)

    @property
    def has_conflicts(self):
        return any(item.status == 'conflict' for item in self.file_status)

    @property
    def total_count(self):
        return len(self.file_status)

    @property
    def staged_count(self):
        return sum(1 for item in self.file_status if item.staged)

    @property
    def unstaged_count(self):
        return sum(1 for item in self.file_status if not item.staged)

    @property
    def untracked_count(self):
        return sum(1 for item in self.file_status
                   if item.status == 'untracked')

    @property
    def conflict_count(self):
        return sum(1 for item in self.file_status
                   if item.status == 'conflict')


class GitBranches(object):
    def __init__(self, branches=None, current_branch=None):
        self.branches = branches or []
        self.current_branch = current_branch


def _parse_ahead_behind(segment):
    ahead = 0
    behind = 0
    if not segment:
        return ahead, behind
    if 'ahead' in segment:
        try:
            ahead = int(segment.split('ahead')[1].split(',')[0].strip())
        except Exception:
            ahead = 0
    if 'behind' in segment:
        try:
            behind = int(segment.split('behind')[1].split(',')[0].strip())
        except Exception:
            behind = 0
    return ahead, behind


def _normalize_branch_name(name):
    if name.startswith('HEAD (detached at '):
        return name.replace('HEAD (detached at ', '').rstrip(')')
    return (
        name.replace('HEAD (no branch)', 'HEAD')
        .replace('No commits yet on ', '')
        .replace('Initial commit on ', '')
    )


def _derive_status(index_status, working_status):
    statuses = set([index_status, working_status])
    if 'U' in statuses:
        return 'conflict'
    if 'R' in statuses:
        return 'renamed'
    if 'C' in statuses:
        return 'copied'
    if 'D' in statuses:
        return 'deleted'
    if 'A' in statuses:
        return 'added'
    if 'M' in statuses:
        return 'modified'
    if 'T' in statuses:
        return 'typechange'
    if '?' in statuses:
        return 'untracked'
    return 'unknown'


def parse_git_status(output):
    lines = [line.rstrip() for line in (output or '').split('\n')
             if line.strip()]
    current_branch = None
    upstream = None
    ahead = 0
    behind = 0
    detached = False
    file_status = []

    if not lines:
        return GitStatus(file_status=file_status)

    branch_line = lines[0]
    if branch_line.startswith('## '):
        branch_info = branch_line[3:]
        ahead_start = branch_info.find(' [')
        branch_part = branch_info if ahead_start == -1 else branch_info[
            :ahead_start]
        ahead_part = None if ahead_start == -1 else branch_info[
            ahead_start + 2:-1]
        normalized = _normalize_branch_name(branch_part)
        is_detached = branch_part.startswith('HEAD (detached at ') or (
            'detached' in branch_part)
        if is_detached or normalized.startswith('HEAD'):
            detached = True
        elif '...' in normalized:
            current_branch, upstream = normalized.split('...', 1)
            current_branch = current_branch or None
            upstream = upstream or None
        else:
            current_branch = normalized or None
        ahead, behind = _parse_ahead_behind(ahead_part)

    for line in lines[1:]:
        if line.startswith('?? '):
            file_status.append(GitFileStatus(
                name=line[3:],
                status='untracked',
                index_status='?',
                working_tree_status='?',
                staged=False,
            ))
            continue
        if len(line) < 3:
            continue
        index_status = line[0]
        working_status = line[1]
        path = line[3:]
        renamed_from = None
        name = path
        if ' -> ' in path:
            renamed_from, name = path.split(' -> ', 1)
        file_status.append(GitFileStatus(
            name=name,
            status=_derive_status(index_status, working_status),
            index_status=index_status,
            working_tree_status=working_status,
            staged=index_status not in (' ', '?'),
            renamed_from=renamed_from,
        ))

    return GitStatus(
        current_branch=current_branch,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        detached=detached,
        file_status=file_status,
    )


def parse_git_branches(output):
    branches = []
    current_branch = None
    for line in [line.strip() for line in (output or '').split('\n')
                 if line.strip()]:
        if '\t' in line:
            name, marker = line.split('\t', 1)
            marker = marker.strip()
        else:
            marker = '*' if line.startswith('* ') else ''
            name = line[2:] if line.startswith('* ') else line
        branches.append(name)
        if marker == '*':
            current_branch = name
    return GitBranches(branches=branches, current_branch=current_branch)


def _is_auth_failure(result):
    message = '{0}\n{1}\n{2}'.format(
        getattr(result, 'stderr', ''),
        getattr(result, 'stdout', ''),
        getattr(result, 'error', ''),
    ).lower()
    snippets = (
        'authentication failed',
        'terminal prompts disabled',
        'could not read username',
        'invalid username or password',
        'access denied',
        'permission denied',
        'not authorized',
    )
    return any(snippet in message for snippet in snippets)


def _is_missing_upstream(result):
    message = '{0}\n{1}\n{2}'.format(
        getattr(result, 'stderr', ''),
        getattr(result, 'stdout', ''),
        getattr(result, 'error', ''),
    ).lower()
    snippets = (
        'has no upstream branch',
        'no upstream branch',
        'no upstream configured',
        'no tracking information for the current branch',
        'no tracking information',
        'set the remote as upstream',
        'set the upstream branch',
        'please specify which branch you want to merge with',
    )
    return any(snippet in message for snippet in snippets)


def _validate_git_url_credentials(url, username, password):
    if not username and not password:
        return None
    if not username or not password:
        raise InvalidArgumentException(
            'Both username and password are required when using Git '
            'credentials.')
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise InvalidArgumentException(
            'Only http(s) Git URLs support username/password credentials.')
    return parsed


def _askpass_script():
    return (
        '#!/bin/sh\n'
        'case "$1" in\n'
        '*Username*) printf "%s\\n" "$GIT_USERNAME" ;;\n'
        '*Password*) printf "%s\\n" "$GIT_PASSWORD" ;;\n'
        '*) printf "\\n" ;;\n'
        'esac\n'
    )


class Git(object):
    def __init__(self, commands):
        self.commands = commands

    def _run_git(self, repo_path, args, **opts):
        if repo_path:
            opts['cwd'] = repo_path
        return self.commands.run('git {0}'.format(' '.join(args)), **opts)

    def _get_remote_url(self, repo_path, remote, **opts):
        opts = dict(opts)
        opts.pop('background', None)
        result = self._run_git(
            repo_path,
            ['remote', 'get-url', shell_quote(remote)],
            **opts
        )
        url = (getattr(result, 'stdout', '') or '').strip()
        if not url:
            raise InvalidArgumentException(
                'Remote "{0}" URL not found in repository.'.format(remote))
        return url

    def _resolve_remote_name(self, repo_path, remote=None, **opts):
        if remote:
            return remote
        opts = dict(opts)
        opts.pop('background', None)
        result = self._run_git(repo_path, ['remote'], **opts)
        remotes = [
            line.strip()
            for line in (getattr(result, 'stdout', '') or '').splitlines()
            if line.strip()
        ]
        if len(remotes) == 1:
            return remotes[0]
        if len(remotes) == 0:
            raise InvalidArgumentException(
                'No remotes found in the repository.')
        raise InvalidArgumentException(
            'Remote is required when using username/password and the '
            'repository has multiple remotes.')

    def _with_remote_credentials(self, repo_path, remote, username, password,
                                 operation, **opts):
        original_url = self._get_remote_url(repo_path, remote, **opts)
        _validate_git_url_credentials(original_url, username, password)
        sandbox = getattr(self.commands, 'sandbox', None)
        filesystem = getattr(sandbox, 'files', None)
        if filesystem is None:
            raise SandboxError(
                'Sandbox filesystem is required for credentialed Git '
                'operations.')
        temp_dir = '/tmp/qiniu-git-auth'
        setup_opts = dict(opts)
        setup_opts.pop('background', None)
        prepare_result = self.commands.run(
            'install -d -m 700 {0}'.format(shell_quote(temp_dir)),
            **setup_opts
        )
        if getattr(prepare_result, 'exit_code', 0):
            return prepare_result
        askpass_path = '{0}/qiniu-git-askpass-{1}'.format(
            temp_dir,
            uuid.uuid4().hex,
        )
        filesystem.write(askpass_path, _askpass_script())
        try:
            chmod_result = self.commands.run(
                'chmod 700 {0}'.format(shell_quote(askpass_path)),
                **setup_opts
            )
            if getattr(chmod_result, 'exit_code', 0):
                _remove_credential_file(filesystem, askpass_path)
                return chmod_result

            auth_opts = dict(opts)
            envs = dict(auth_opts.get('envs') or {})
            envs.update({
                'GIT_ASKPASS': askpass_path,
                'GIT_TERMINAL_PROMPT': '0',
                'GIT_USERNAME': username,
                'GIT_PASSWORD': password,
            })
            auth_opts['envs'] = envs

            result = operation(auth_opts)
            if opts.get('background') and hasattr(result, 'wait'):
                result.wait = _cleanup_after_wait(
                    result.wait, filesystem, askpass_path)
            else:
                _remove_credential_file(filesystem, askpass_path)
            return result
        except BaseException as err:
            _remove_credential_file(filesystem, askpass_path)
            raise err

    def _raise_known_result_error(
            self, result, operation, throw_on_error=False):
        if (getattr(result, 'exit_code', None) == -1 and
                hasattr(result, 'wait')):
            if throw_on_error:
                result.wait = self._raise_after_wait(result.wait, operation)
            return
        if not hasattr(result, 'exit_code'):
            return
        if result.exit_code:
            if _is_auth_failure(result):
                raise GitAuthException(
                    'Git {0} requires credentials for private repositories.'
                    .format(operation))
            if _is_missing_upstream(result):
                raise GitUpstreamException(
                    'Git {0} failed because no upstream branch is configured.'
                    .format(operation))
            if throw_on_error:
                raise CommandExitError(result)

    def _raise_after_wait(self, wait, operation):
        def wrapped_wait(*args, **kwargs):
            result = wait(*args, **kwargs)
            self._raise_known_result_error(
                result, operation, throw_on_error=True)
            return result
        return wrapped_wait

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
        result = self._run_git(
            repo_path, [
                'status', '--porcelain=1', '-b'], **opts)
        if result.exit_code:
            raise CommandExitError(result)
        return parse_git_status(result.stdout)

    def add(self, repo_path, files=None, all=False, **opts):
        args = ['add']
        if all:
            args.append('--all')
        else:
            args.append('--')
            for path in _normalize_paths(files) or ['.']:
                args.append(shell_quote(path))
        return self._run_git(repo_path, args, **opts)

    def commit(self, repo_path, message, author_name=None, author_email=None,
               allow_empty=False, **opts):
        args = []
        if author_name:
            args.extend(['-c', shell_quote('user.name={0}'.format(
                author_name))])
        if author_email:
            args.extend(['-c', shell_quote('user.email={0}'.format(
                author_email))])
        args.extend(['commit', '-m', shell_quote(message)])
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

    def pull(self, repo_path, remote=None, branch=None, username=None,
             password=None, **opts):
        throw_on_error = opts.pop('throw_on_error', False)
        if password and not username:
            raise InvalidArgumentException(
                'Git pull requires username when password is provided')
        remote_name = None
        if username and password:
            remote_name = self._resolve_remote_name(repo_path, remote, **opts)

        args = ['pull']
        target_remote = remote_name or remote
        if target_remote:
            args.append(shell_quote(target_remote))
        if branch:
            args.append(shell_quote(branch))
        if username and password:
            result = self._with_remote_credentials(
                repo_path,
                remote_name,
                username,
                password,
                lambda auth_opts: self._run_git(
                    repo_path, args, throw_on_error=False, **auth_opts),
                **opts
            )
            self._raise_known_result_error(
                result, 'pull', throw_on_error=throw_on_error)
            return result

        result = self._run_git(repo_path, args, throw_on_error=False, **opts)
        self._raise_known_result_error(
            result, 'pull', throw_on_error=throw_on_error)
        return result

    def push(self, repo_path, remote=None, branch=None, set_upstream=True,
             username=None, password=None, **opts):
        throw_on_error = opts.pop('throw_on_error', False)
        if password and not username:
            raise InvalidArgumentException(
                'Git push requires username when password is provided')
        remote_name = None
        if username and password:
            remote_name = self._resolve_remote_name(repo_path, remote, **opts)

        args = ['push']
        target_remote = remote_name or remote
        if set_upstream and target_remote:
            args.append('--set-upstream')
        if target_remote:
            args.append(shell_quote(target_remote))
        if branch:
            args.append(shell_quote(branch))
        if username and password:
            result = self._with_remote_credentials(
                repo_path,
                remote_name,
                username,
                password,
                lambda auth_opts: self._run_git(
                    repo_path, args, throw_on_error=False, **auth_opts),
                **opts
            )
            self._raise_known_result_error(
                result, 'push', throw_on_error=throw_on_error)
            return result

        result = self._run_git(repo_path, args, throw_on_error=False, **opts)
        self._raise_known_result_error(
            result, 'push', throw_on_error=throw_on_error)
        return result

    def dangerously_authenticate(
            self,
            username,
            password,
            host='github.com',
            protocol='https',
            **opts):
        opts = dict(opts)
        opts.pop('background', None)
        if not username:
            raise InvalidArgumentException('username is required')
        if not password:
            raise InvalidArgumentException('password is required')

        result = self._run_git(
            None,
            ['config', '--global', 'credential.helper', 'store'],
            **opts
        )
        if result.exit_code != 0:
            return result

        credential = (
            'protocol={0}\n'
            'host={1}\n'
            'username={2}\n'
            'password={3}\n\n'
        ).format(protocol, host, username, password)
        handle = self.commands.run(
            'git credential approve',
            stdin=True,
            background=True,
            **opts
        )
        self.commands.send_stdin(handle.pid, credential)
        self.commands.close_stdin(handle.pid)
        return handle.wait()

    dangerouslyAuthenticate = dangerously_authenticate

    def remote_add(self, repo_path, name, url, **opts):
        fetch = opts.pop('fetch', False)
        overwrite = opts.pop('overwrite', False)
        if overwrite:
            self._run_git(repo_path, [
                'remote',
                'remove',
                shell_quote(name),
            ], **opts)
        result = self._run_git(repo_path, [
            'remote',
            'add',
            shell_quote(name),
            shell_quote(url),
        ], **opts)
        if result.exit_code != 0 or not fetch:
            return result
        return self._run_git(repo_path, [
            'fetch',
            shell_quote(name),
        ], **opts)

    remoteAdd = remote_add

    def remote_get(self, repo_path, name='origin', **opts):
        return self._run_git(repo_path, [
            'remote',
            'get-url',
            shell_quote(name),
        ], **opts)

    remoteGet = remote_get

    def branches(self, repo_path, **opts):
        result = self._run_git(
            repo_path,
            ['branch', shell_quote('--format=%(refname:short)\t%(HEAD)')],
            **opts
        )
        return parse_git_branches(result.stdout)

    def create_branch(self, repo_path, name, start_point=None, **opts):
        args = ['checkout', '-b', shell_quote(name)]
        if start_point:
            args.append(shell_quote(start_point))
        return self._run_git(repo_path, args, **opts)

    createBranch = create_branch

    def checkout_branch(self, repo_path, name, create=False, **opts):
        args = ['checkout']
        if create:
            args.append('-b')
        args.append(shell_quote(name))
        return self._run_git(repo_path, args, **opts)

    checkoutBranch = checkout_branch

    def delete_branch(self, repo_path, name, force=True, **opts):
        return self._run_git(repo_path, [
            'branch',
            '-D' if force else '-d',
            shell_quote(name),
        ], **opts)

    deleteBranch = delete_branch

    def reset(self, repo_path, target=None, mode=None, **opts):
        args = ['reset']
        mode = mode or opts.get('reset_type') or opts.get('resetType')
        if mode:
            if mode not in RESET_MODES:
                raise InvalidArgumentException(
                    'Unsupported git reset mode: {0}'.format(mode)
                )
            args.append('--{0}'.format(mode))
        if target:
            args.append(shell_quote(target))
        return self._run_git(repo_path, args, **opts)

    def restore(self, repo_path, paths=None, staged=False, source=None,
                **opts):
        args = ['restore']
        if staged:
            args.append('--staged')
        if source:
            args.extend(['--source', shell_quote(source)])
        paths = paths if paths is not None else opts.get('files')
        args.append('--')
        for path in _normalize_paths(paths) or ['.']:
            args.append(shell_quote(path))
        return self._run_git(repo_path, args, **opts)

    def set_config(self, key, value, scope='global', path=None, **opts):
        """Set a Git config value.

        Preferred signature:
            set_config(key, value, scope='global', path=None, **opts)

        For local config, pass scope='local' and path=repo_path. For backward
        compatibility this method also accepts the deprecated signature:
            set_config(repo_path, key, value, global_config=False, **opts)
        """
        key, value, scope, path = self._normalize_set_config_args(
            key, value, scope, path, opts)
        scope_flag, repo_path = self._resolve_config_scope(scope, path)
        args = ['config']
        if scope_flag:
            args.append(scope_flag)
        args.extend([shell_quote(key), shell_quote(value)])
        return self._run_git(repo_path, args, **opts)

    setConfig = set_config

    def get_config(self, key, scope='global', path=None, **opts):
        """Get a Git config value.

        Preferred signature:
            get_config(key, scope='global', path=None, **opts)

        For local config, pass scope='local' and path=repo_path. For backward
        compatibility this method also accepts the deprecated signature:
            get_config(repo_path, key, global_config=False, **opts)
        """
        key, scope, path = self._normalize_get_config_args(
            key, scope, path, opts)
        scope_flag, repo_path = self._resolve_config_scope(scope, path)
        args = ['config']
        if scope_flag:
            args.append(scope_flag)
        args.extend(['--get', shell_quote(key)])
        return self._run_git(repo_path, args, **opts)

    getConfig = get_config

    def _normalize_set_config_args(self, key, value, scope, path, opts):
        global_config = opts.pop(
            'global_config', opts.pop('globalConfig', False))
        if global_config or self._is_legacy_config_call(scope):
            repo_path = key
            key = value
            value = scope
            scope = 'global' if global_config or repo_path is None else 'local'
            path = None if scope == 'global' else repo_path
        return key, value, scope, path

    def _normalize_get_config_args(self, key, scope, path, opts):
        global_config = opts.pop(
            'global_config', opts.pop('globalConfig', False))
        if global_config or self._is_legacy_config_call(scope):
            repo_path = key
            key = scope
            scope = 'global' if global_config or repo_path is None else 'local'
            path = None if scope == 'global' else repo_path
        return key, scope, path

    def _is_legacy_config_call(self, scope):
        if scope is None:
            return False
        return str(scope).strip().lower() not in ('global', 'local', 'system')

    def _resolve_config_scope(self, scope=None, path=None):
        scope_name = (scope or 'global').strip().lower()
        if scope_name not in ('global', 'local', 'system'):
            raise InvalidArgumentException(
                'Git config scope must be global, local, or system')
        if scope_name == 'local':
            if not path:
                raise InvalidArgumentException(
                    'Repository path is required for local scope')
            return '--local', path
        if scope_name == 'system':
            return '--system', None
        return '--global', None
