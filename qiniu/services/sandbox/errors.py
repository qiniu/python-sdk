# -*- coding: utf-8 -*-


class SandboxError(Exception):
    def __init__(self, message, response=None, data=None):
        super(SandboxError, self).__init__(message)
        self.response = response
        self.data = data
        self.status_code = getattr(response, 'status_code', None)


class TemplateBuildError(SandboxError):
    pass


class CommandExitError(SandboxError):
    def __init__(self, result):
        self.result = result
        super(CommandExitError, self).__init__(
            'Command exited with code {0}'.format(result.exit_code)
        )
