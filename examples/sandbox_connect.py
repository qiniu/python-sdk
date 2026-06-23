# -*- coding: utf-8 -*-
from __future__ import print_function

from qiniu.services.sandbox import Sandbox
from sandbox_common import (
    cleanup_sandbox,
    create_sandbox,
    run_example,
    sandbox_client,
)


def main():
    client = sandbox_client()
    sandbox = create_sandbox(
        client=client,
        timeout=300,
        metadata={'example': 'sandbox_connect'},
    )
    try:
        items = Sandbox.list(client=client, limit=10).next_items()
        print('list:', [item.sandbox_id for item in items])

        connected = Sandbox.connect(
            sandbox.sandbox_id,
            client=client,
            timeout=300,
        )
        print('connected:', connected.sandbox_id)
        print('envd:', connected.envd_url())
        print('uptime:', connected.commands.run('uptime').stdout)
    finally:
        cleanup_sandbox(sandbox)


if __name__ == '__main__':
    run_example(main)
