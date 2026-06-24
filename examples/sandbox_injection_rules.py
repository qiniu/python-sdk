# -*- coding: utf-8 -*-
from __future__ import print_function

from sandbox_common import run_example, sandbox_client


def main():
    client = sandbox_client()
    rule_id = None
    try:
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
        print('get:', client.get_injection_rule(rule_id))
        print('updated:', client.update_injection_rule(
            rule_id,
            name='python-sdk-example-updated',
            injection={
                'type': 'http',
                'base_url': 'https://api.example.com',
                'headers': {'X-Updated-From-Sandbox': 'qiniu-python-sdk'},
            },
        ))
    finally:
        if rule_id:
            client.delete_injection_rule(rule_id)
            print('deleted:', rule_id)


if __name__ == '__main__':
    run_example(main)
