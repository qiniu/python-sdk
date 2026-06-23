# -*- coding: utf-8 -*-
import json

from .util import shell_quote


class ReadyCmd(object):
    def __init__(self, cmd):
        self._cmd = cmd

    def get_cmd(self):
        return self._cmd


def wait_for_port(port):
    port = int(port)
    return ReadyCmd(
        "ss -tuln | awk '{{print $5}}' | grep -E '(^|:){0}$'".format(
            port))


def wait_for_url(url, status_code=200):
    status_code = int(status_code)
    return ReadyCmd(
        '[ "$(curl -s -o /dev/null -w "%{{http_code}}" {0})" = "{1}" ]'.format(
            shell_quote(url),
            status_code,
        )
    )


def wait_for_process(process_name):
    return ReadyCmd('pgrep {0} > /dev/null'.format(shell_quote(process_name)))


def wait_for_file(filename):
    return ReadyCmd('[ -f {0} ]'.format(shell_quote(filename)))


def wait_for_timeout(timeout):
    seconds = max(1, int(timeout) // 1000)
    return ReadyCmd('sleep {0}'.format(seconds))


def _ready_cmd_value(command):
    if hasattr(command, 'get_cmd'):
        return command.get_cmd()
    return command


class Template(object):
    def __init__(self):
        self.build_config = {'steps': []}

    def from_image(self, image, credentials=None):
        self.build_config['fromImage'] = image
        self.build_config.pop('fromTemplate', None)
        if credentials:
            self.build_config['fromImageRegistry'] = credentials
        return self

    fromImage = from_image

    def from_template(self, template_id):
        self.build_config['fromTemplate'] = template_id
        self.build_config.pop('fromImage', None)
        self.build_config.pop('fromImageRegistry', None)
        return self

    fromTemplate = from_template

    def add_step(self, step_type, args, **extra):
        step = {'type': step_type, 'args': [str(arg) for arg in args]}
        step.update(extra)
        self.build_config['steps'].append(step)
        return self

    addStep = add_step

    def run_cmd(self, command, user=None):
        if isinstance(command, (list, tuple)):
            command = ' '.join(shell_quote(arg) for arg in command)
        args = [command]
        if user:
            args.append(user)
        return self.add_step('RUN', args)

    run = run_cmd
    runCmd = run_cmd

    def copy(self, src, dest, chmod=None, chown=None):
        extra = {}
        if chmod is not None:
            extra['chmod'] = str(chmod)
        if chown is not None:
            extra['chown'] = chown
        return self.add_step('COPY', [src, dest], **extra)

    def set_env(self, key, value):
        return self.add_step('ENV', [key, value])

    setEnv = set_env

    def set_start_cmd(self, command, ready_cmd=None):
        self.build_config['startCmd'] = command
        if ready_cmd is not None:
            self.build_config['readyCmd'] = _ready_cmd_value(ready_cmd)
        return self

    setStartCmd = set_start_cmd

    def set_ready_cmd(self, command):
        self.build_config['readyCmd'] = _ready_cmd_value(command)
        return self

    setReadyCmd = set_ready_cmd

    def to_dict(self):
        data = dict(self.build_config)
        data['steps'] = list(self.build_config.get('steps', []))
        return data

    def to_json(self):
        return json.dumps(self.to_dict(), separators=(',', ':'))

    toJSON = to_json
