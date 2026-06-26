# -*- coding: utf-8 -*-
from __future__ import print_function

import time

from qiniu.services.sandbox import (
    SandboxError,
    Template,
    wait_for_file,
    wait_for_port,
    wait_for_process,
    wait_for_timeout,
    wait_for_url,
)
from sandbox_common import run_example, sandbox_client


def pick(data, *keys):
    for key in keys:
        if isinstance(data, dict) and data.get(key) is not None:
            return data.get(key)
    return None


def main():
    client = sandbox_client()
    name = 'qiniu-python-sdk-example-{0}'.format(int(time.time() * 1000))
    target = '{0}:v1'.format(name)
    template_id = None

    builder_demo = (
        Template()
        .from_template('base')
        .copy('README.md', '/tmp/README.md', chmod='0644')
        .set_ready_cmd(wait_for_file('/tmp/README.md'))
    )
    print('builder demo:', builder_demo.to_dict())

    config_demo = (
        Template()
        .from_image('python:3.11')
        .run_cmd(['python', '--version'])
        .set_env('PYTHONUNBUFFERED', '1')
        .set_start_cmd(
            'python -m http.server 8000',
            ready_cmd=wait_for_port(8000),
        )
        .set_ready_cmd(wait_for_timeout(1000))
        .to_dict()
    )
    print('config demo:', config_demo)
    print('ready helpers:', [
        wait_for_file('/tmp/README.md').get_cmd(),
        wait_for_process('python').get_cmd(),
        wait_for_url('http://127.0.0.1:8000').get_cmd(),
    ])

    try:
        created = client.create_template(name=target)
        template_id = pick(
            created,
            'templateID',
            'templateId',
            'template_id',
            'id',
        ) or name
        build_id = pick(created, 'buildID', 'buildId', 'build_id')
        print('created:', template_id)

        print('default templates:', len(client.list_default_templates()))
        print('templates:', len(client.list_templates()))
        print('get:', client.get_template(template_id))

        updated = client.update_template(
            template_id,
            description='Created by qiniu-python-sdk example',
        )
        print('updated:', updated)

        if build_id:
            print('build status:', client.get_template_build_status(
                template_id,
                build_id,
            ))
            print('build logs:', client.get_template_build_logs(
                template_id,
                build_id,
            ))
            client.start_template_build(
                template_id,
                build_id,
                fromTemplate='base',
            )
            print('build started:', build_id)
            final_build = client.wait_for_build(
                template_id,
                build_id,
                interval=3,
                timeout=120,
            )
            print(
                'wait build:',
                final_build.get('status'),
                'logs:',
                len(final_build.get('logs') or []),
            )

        client.assign_template_tags(
            target=target,
            tags=['example'],
        )
        print('tagged:', template_id)
        client.delete_template_tags(name=name, tags=['example'])
        print('untagged:', template_id)
    except SandboxError as err:
        print('template lifecycle skipped:', err)
    finally:
        if template_id:
            try:
                client.delete_template(template_id)
                print('deleted:', template_id)
            except SandboxError as err:
                print('delete template skipped:', err)


if __name__ == '__main__':
    run_example(main)
