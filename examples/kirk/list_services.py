# -*- coding: utf-8 -*-
# flake8: noqa

import sys
from qiniu import QiniuMacAuth
from qiniu import AccountClient

access_key = sys.argv[1]
secret_key = sys.argv[2]

acc_client = AccountClient(QiniuMacAuth(access_key, secret_key))
apps, info = acc_client.list_apps()

for app in apps:
    if app.get('runMode') == 'Private':
        uri = app.get('uri')
        qcos = acc_client.get_qcos_client(uri)
        if qcos != None:
            stacks, info = qcos.list_stacks()
            for stack in stacks:
                stack_name = stack.get('name')
                services, info = qcos.list_services(stack_name)
                print("list_services of '%s : %s':"%(uri, stack_name))
                print(services)
                print(info)
                assert len(services) is not None
