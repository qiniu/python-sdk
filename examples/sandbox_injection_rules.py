# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import run_example, sandbox_client


def main():
    client = sandbox_client()
    rule = client.create_injection_rule(
        name='python-sdk-example',
        injection={
            'type': 'http',
            'base_url': 'https://api.example.com',
            'headers': {'X-From-Sandbox': 'qiniu-python-sdk'},
        },
    )
    print('created:', rule)
    rules = client.list_injection_rules()
    print('rules count:', len(rules))
    rule_id = rule.get('id') or rule.get('ruleID')
    client.delete_injection_rule(rule_id)
    print('deleted:', rule_id)


if __name__ == '__main__':
    run_example(main)
