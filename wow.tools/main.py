import base64
import json
import bs4
import requests
from google.cloud import pubsub_v1
from google.cloud import storage

LOCALES = [
    'deDE', 'enGB', 'enUS', 'esES', 'esMX', 'frFR', 'itIT',
    'koKR', 'ptBR', 'ptPT', 'ruRU', 'zhCN', 'zhTW',
]

storage_client = storage.Client()
bucket = storage_client.bucket('wowdb-import-stage')
ps = pubsub_v1.PublisherClient()

def fetch(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response

def latest_classic_version():
    data = fetch('https://wow.tools/dbc/').text
    soup = bs4.BeautifulSoup(data, 'html.parser')
    for v in soup.find('select', id='lockedBuild').find_all('option'):
        s = v.string.split(' ', 1)
        if len(s) == 2 and s[1] == '(ClassicRetail)':
            return s[0]
    raise Exception('no version')

def http_publish(_):
    print('fetching classic version...')
    v = latest_classic_version()
    print('using classic version', v)
    print('getting wow.tools table list...')
    dbcs = set(
        e['name']
        for e in fetch(f'https://api.wow.tools/databases/{v}').json())
    topic = ps.topic_path('wow-ferronn-dev', 'wow-tools-dbc')
    futures = [
        ps.publish(topic, json.dumps({
            'v': v, 'dbc': dbc, 'loc': loc,
        }).encode('ascii'))
        for dbc in dbcs
        for loc in LOCALES
    ]
    results = [f.result() for f in futures]
    msg = f'published {len(results)} messages'
    print(msg)
    return msg

def pubsub_dbc(event, _):
    data = json.loads(base64.b64decode(event['data']))
    [v, dbc, loc] = [data[k] for k in ['v', 'dbc', 'loc']]
    print('using classic version', v)
    print('working on', dbc)
    print('for locale', loc)
    b = bucket.blob(f'wow_tools_dbc_{v.replace(".", "_")}_{loc}/{dbc}.csv')
    if b.exists():
        print('blob already exists')
        return
    print('fetching schema...')
    b.metadata = {
        'headers': json.dumps([
            header.replace('[', '_').replace(']', '_').lower()
            for header in fetch(
                f'https://wow.tools/dbc/api/header/{dbc}/',
                {'build': v},
            ).json()['headers']]),
    }
    print('fetching csv...')
    csv = fetch('https://wow.tools/dbc/api/export/', {
        'name': dbc,
        'build': v,
        'locale': loc,
    }).text
    print('uploading csv...')
    b.upload_from_string(csv)
    print('all done with', dbc)
