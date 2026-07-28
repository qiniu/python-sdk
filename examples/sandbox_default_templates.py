# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import run_example, sandbox_client


def main():
    client = sandbox_client()
    templates = client.list_default_templates()

    print('default templates:', len(templates))
    for template in templates:
        print(
            '  - {0} (names: {1}, build status: {2})'.format(
                template.get('templateID'),
                template.get('names') or [],
                template.get('buildStatus'),
            )
        )


if __name__ == '__main__':
    run_example(main)
