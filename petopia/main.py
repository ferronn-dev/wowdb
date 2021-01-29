import bs4
import json
import pprint
import requests
from google.cloud import bigquery
from google.cloud import storage

def parse(soup):
    return [{
        'name': ability.find_previous_sibling('h3').text,
        'families': [
            family.text
            for family in ability \
                .find_previous_sibling('p') \
                .find_all('span')[-1] \
                .find_all('a')
        ],
        'ranks': [
            (lambda info=rank.next_sibling.string.split(' '): {
                'rank': int(rank.text.rpartition(' ')[-1]),
                'petlevel': int(info[3][:-1]),
                'cost': int(info[5]),
                'trainers': [
                    (lambda parts=npc.text.split(', '):
                    (lambda lvls=parts[1].split('-'): {
                        'npc': int(npc.a['href'].split('=')[-1]),
                        'minlevel': int(lvls[0]),
                        'maxlevel': int(lvls[-1]),
                        'zone': parts[2][:-1],
                    })())()
                    for npc in rank.parent.find_all(class_='abilityranknpc classic')
                ],
            })()
            for rank in ability.find_all(class_='abilityrankname classic')
        ],
    } for ability in soup.find_all(class_='abilityranklist classic')]

def flatten(abilities):
    return {
        'families': [
            {
                'ability': ability['name'],
                'family': family,
            }
            for ability in abilities
            for family in ability['families']
        ],
        'ranks': [
            {
                'ability': ability['name'],
                'rank': rank['rank'],
                'petlevel': rank['petlevel'],
                'cost': rank['cost'],
            }
            for ability in abilities
            for rank in ability['ranks']
        ],
        'trainers': [
            {
                'ability': ability['name'],
                'rank': rank['rank'],
                **trainer,
            }
            for ability in abilities
            for rank in ability['ranks']
            for trainer in rank['trainers']
        ],
    }

def scrape(_):
    data = requests.get('https://www.wow-petopia.com/classic/abilities.php')
    data.raise_for_status()
    soup = bs4.BeautifulSoup(data.text, 'html.parser')
    bigquery_client = bigquery.Client('wow-ferronn-dev')
    dataset = bigquery_client.create_dataset('wow-ferronn-dev.petopia', exists_ok=True)
    bucket = storage.Client().bucket('wow.ferronn.dev')
    for name, db in flatten(parse(soup)).items():
        ndjson = '\n'.join([json.dumps(record) for record in db])
        bucket.blob(f'petopia/{name}.json').upload_from_string(ndjson)
        job = bigquery_client.load_table_from_uri(
            source_uris=f'gs://wow.ferronn.dev/petopia/{name}.json',
            destination=dataset.table(name),
            job_config=bigquery.LoadJobConfig(
                autodetect=True,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE))
        job.result()
    return f'finished petopia scrape'
