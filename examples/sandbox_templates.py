# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import Template
from sandbox_common import run_example, sandbox_client


def main():
    client = sandbox_client()
    template = (
        Template()
        .from_image('python:3.11')
        .run_cmd('python --version')
        .set_env('PYTHONUNBUFFERED', '1')
    )

    created = client.create_template(
        name='qiniu-python-sdk-example',
        buildConfig=template.to_dict(),
    )
    print('template:', created)


if __name__ == '__main__':
    run_example(main)
