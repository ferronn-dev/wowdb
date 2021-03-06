import bs4
import json
import requests
from google.cloud import storage

def removesuffix(string, suffix):
    return string[:-len(suffix)] if string.endswith(suffix) else string

def parse_zone(zone):
    return removesuffix(removesuffix(zone, ' (Dungeon)'), ' (Raid)')

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
                'purchasable': bool(rank.parent.find_all(string='Can be learned from trainers.')),
                'trainers': [
                    (lambda parts=npc.text.split(', '):
                    (lambda lvls=parts[1].split('-'): {
                        'npc': int(npc.a['href'].split('=')[-1]),
                        'minlevel': int(lvls[0]),
                        'maxlevel': int(lvls[-1]),
                        'zones': [parse_zone(z) for z in parts[2][:-1].split('; ')],
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
                'purchasable': rank['purchasable'],
            }
            for ability in abilities
            for rank in ability['ranks']
        ],
        'trainers': [
            {
                'ability': ability['name'],
                'rank': rank['rank'],
                'npc': trainer['npc'],
                'minlevel': trainer['minlevel'],
                'maxlevel': trainer['maxlevel'],
                'zone': zone,
            }
            for ability in abilities
            for rank in ability['ranks']
            for trainer in rank['trainers']
            for zone in trainer['zones']
        ],
    }

versions = [
    ('classic', ''),
    ('classic_bc', '_bc'),
]

def data(path):
    data = requests.get(f'https://www.wow-petopia.com/{path}/abilities.php')
    data.raise_for_status()
    soup = bs4.BeautifulSoup(data.text, 'html.parser')
    return flatten(parse(soup))

def scrape(_):
    bucket = storage.Client().bucket('wowdb-import-stage')
    for path, suffix in versions:
        for name, db in data(path).items():
            ndjson = '\n'.join([json.dumps(record) for record in db])
            bucket.blob(f'petopia{suffix}/{name}.json').upload_from_string(ndjson)
    return 'finished petopia scrape'
