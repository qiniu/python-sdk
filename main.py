from qiniu import Auth, DomainManager

access_key = ''
secret_key = ''

at = Auth(access_key, secret_key)

dm = DomainManager(at)

for ret, resp_info in dm.get_domain_list(limit=100):
    for domain in ret['domains']:
        print(domain['name'])
