import json
import oauthlib
import requests
import requests_oauthlib
import time
from google.cloud import secretmanager

secret_client = secretmanager.SecretManagerServiceClient()
[client_id, client_secret] = [
    secret_client.access_secret_version(request={
        'name': f'projects/wow-ferronn-dev/secrets/{secret}/versions/latest'
    }).payload.data
    for secret in [f'battle-net-oauth-client-{x}' for x in ['id', 'secret']]
]
print('retrieved secrets')

client = oauthlib.oauth2.BackendApplicationClient(client_id=client_id)
oauth = requests_oauthlib.OAuth2Session(client=client)
token = oauth.fetch_token(
    token_url='https://us.battle.net/oauth/token',
    client_id=client_id,
    client_secret=client_secret)
wowtoken = token['access_token']
print('retrieved wow api access token')

def wow_api(endpoint, extra):
    time.sleep(0.05)
    ns = 'static-classic-us'
    path = f'https://us.api.blizzard.com/data/wow/{endpoint}'
    query = f'namespace={ns}&access_token={wowtoken}'
    return requests.get(f'{path}?{query}{extra}').json()

def wow_fetch(endpoint):
    return wow_api(endpoint, '')

def wow_search(endpoint):
    results = []
    data = wow_api(endpoint, '&_pageSize=1000&orderby=id')
    while 'resultCountCapped' in data:
        results = results + [r['data'] for r in data['results']]
        last = results[-1]['id']
        data = wow_api(endpoint, f'&_pageSize=1000&orderby=id&id=({last},)')
    return results + [r['data'] for r in data['results']]

def scrape(_):
    data = {
        tname: [
            { 'id': d['id'], 'lang': lang, 'name': name }
            for d in tdata for lang, name in d['name'].items()
        ]
        for tname, tdata in {
            'creature-families': wow_fetch('creature-family/index')['creature_families'],
            'creature-types': wow_fetch('creature-type/index')['creature_types'],
            'creatures': wow_search('search/creature'),
        }.items()
    }
    print('retrieved data')
    for name, values in data.items():
        with open(f'{name}.json', 'w') as f:
            f.write('\n'.join([json.dumps(v) for v in values]))
            print(f'wrote {name}.json')
    print('all done')
    return 'success'
