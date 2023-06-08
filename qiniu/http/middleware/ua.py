import platform as _platform

from .base import Middleware


class UserAgentMiddleware(Middleware):
    def __init__(self, sdk_version):
        sys_info = '{0}; {1}'.format(_platform.system(), _platform.machine())
        python_ver = _platform.python_version()

        user_agent = 'QiniuPython/{0} ({1}; ) Python/{2}'.format(
            sdk_version, sys_info, python_ver)

        self.user_agent = user_agent

    def __call__(self, request, nxt):
        if not request.headers:
            request.headers = {}
        request.headers['User-Agent'] = self.user_agent
        return nxt(request)
