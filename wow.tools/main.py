import base64
import bs4
import json
import pprint
import requests
from google.cloud import bigquery
from google.cloud import pubsub_v1
from google.cloud import storage

def latest_classic_version():
    data = requests.get('https://wow.tools/dbc/')
    data.raise_for_status()
    soup = bs4.BeautifulSoup(data.text, 'html.parser')
    for v in soup.find('select', id='lockedBuild').find_all('option'):
        s = v.string.split(' ', 1)
        if len(s) == 2 and s[1] == '(ClassicRetail)':
            return s[0]
    raise Exception('no version')

def get_blob(name, build):
    client = storage.Client()
    bucket = client.bucket('wow.ferronn.dev')
    return bucket.blob(f'wow.tools/dbc/{build}/{name}.csv')

def pull_csv(name, build):
    base = 'https://wow.tools/dbc/api/export/'
    data = requests.get(f'{base}?name={name}&build={build}&locale=enUS')
    data.raise_for_status()
    return data.text

def pull_schema(name, build):
    base = 'https://wow.tools/dbc/api/header'
    data = requests.get(f'{base}/{name}/?build={build}')
    data.raise_for_status()
    return data.json()

def pull_db(build):
    base = 'https://api.wow.tools/databases'
    data = requests.get(f'{base}/{build}')
    data.raise_for_status()
    return data.json()

def connect_to_bq(v):
    print('connecting to bigquery...')
    bq = bigquery.Client('wow-ferronn-dev')
    ds = bq.create_dataset('wow-ferronn-dev.wow_tools_dbc_' + v.replace('.', '_'), exists_ok=True)
    return bq, ds

def http_publish(req):
    print('fetching classic version...')
    v = latest_classic_version()
    print('using classic version', v)
    bq, ds = connect_to_bq(v)
    print('getting wow.tools table list...')
    dbcs = set(e['name'] for e in pull_db(v))
    print('listing bigquery tables...')
    bqt = set(t.table_id for t in bq.list_tables(ds))
    ps = pubsub_v1.PublisherClient()
    topic = ps.topic_path('wow-ferronn-dev', 'wow-tools-dbc')
    futures = [
        ps.publish(topic, json.dumps({'v': v, 'dbc': dbc}).encode('ascii'))
        for dbc in (dbcs - bqt)
    ]
    results = [f.result() for f in futures]
    msg = f'published {len(results)} messages'
    print(msg)
    return msg

def pubsub_dbc(event, ctx):
    data = json.loads(base64.b64decode(event['data']))
    v = data['v']
    dbc = data['dbc']
    print('using classic version', v)
    print('working on', dbc)
    b = get_blob(dbc, v)
    if b.exists():
        print('blob already exists')
    else:
        print('fetching csv...')
        d = pull_csv(dbc, v)
        print('uploading csv...')
        b.upload_from_string(d)
    print('fetching schema...')
    schema = [
        bigquery.schema.SchemaField(
            name=h.replace('[', '_').replace(']', '_').lower(),
            field_type='STRING',
        ) for h in pull_schema(dbc, v)['headers']
    ]
    pprint.pprint(schema)
    print('creating bq table...')
    bq, ds = connect_to_bq(v)
    job = bq.load_table_from_uri(
        f'gs://wow.ferronn.dev/wow.tools/dbc/{v}/{dbc}.csv',
        ds.table(dbc),
        job_config=bigquery.job.LoadJobConfig(
            allow_quoted_newlines=True,
            autodetect=False,
            schema=schema,
            skip_leading_rows=1,
            write_disposition='WRITE_EMPTY'))
    job.result()
    print('all done with', dbc)
