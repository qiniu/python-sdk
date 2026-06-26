# -*- coding: utf-8 -*-
from __future__ import print_function
import os

from qiniu.services.sandbox import Sandbox
from qiniu.services.sandbox.config import (
    env,
    load_dotenv_if_present,
    required_env,
    sandbox_client,
    sandbox_template,
)


__all__ = [
    'cleanup_sandbox',
    'create_sandbox',
    'env',
    'load_example_env',
    'required_env',
    'run_example',
    'sandbox_client',
    'sandbox_template',
]


def load_example_env():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    load_dotenv_if_present(
        os.path.join(root, '.env'),
        os.path.join(os.getcwd(), '.env'),
    )


def create_sandbox(**options):
    client = options.pop('client', None) or sandbox_client()
    template = options.pop('template', sandbox_template())
    options.setdefault('timeout', 300)
    sandbox = Sandbox.create(template, client=client, **options)
    print('Sandbox created:', sandbox.sandbox_id)
    return sandbox


def cleanup_sandbox(sandbox):
    if sandbox is None:
        return
    try:
        sandbox.kill()
        print('Sandbox killed:', sandbox.sandbox_id)
    except Exception as err:
        print('Failed to kill sandbox:', sandbox.sandbox_id, err)


def run_example(fn):
    load_example_env()
    try:
        fn()
    except Exception as err:
        print(err)
        raise
