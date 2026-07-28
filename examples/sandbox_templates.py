# -*- coding: utf-8 -*-
from __future__ import print_function

import time

from qiniu.services.sandbox import SandboxError
from qiniu.services.sandbox import Template
from sandbox_common import run_example, sandbox_client


def main():
    client = sandbox_client()
    template_id = None
    template = (
        Template()
        .from_image('python:3.11')
        .run_cmd('python --version')
        .set_env('PYTHONUNBUFFERED', '1')
    )

    default_templates = client.list_default_templates()
    print('default templates:', len(default_templates))
    for default_template in default_templates:
        print(
            '  - {0} (names: {1}, build status: {2})'.format(
                default_template.get('templateID'),
                default_template.get('names') or [],
                default_template.get('buildStatus'),
            )
        )

    try:
        created = client.create_template(
            name='qiniu-python-sdk-example-{0}'.format(
                int(time.time() * 1000),
            ),
            buildConfig=template.to_dict(),
        )
        template_id = (
            created.get('templateID') or
            created.get('templateId') or
            created.get('id')
        )
        print('template:', created)
        details = client.get_template(template_id)
        print('names:', details.get('names'))
        print('owned by requesting team:', details.get('isOwner'))
    finally:
        if template_id:
            try:
                client.delete_template(template_id)
                print('deleted:', template_id)
            except SandboxError as err:
                print('delete template skipped:', err)


if __name__ == '__main__':
    run_example(main)
