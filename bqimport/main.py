import re
from google.cloud import bigquery

project = 'wow-ferronn-dev'
bigquery_client = bigquery.Client(project)

def bqimport(event, _):
    dname, tname, ext = re.match(r'([^/]+)/(.+)\.(.+)$', event['name']).groups()
    assert ext == 'json'
    dataset = bigquery_client.create_dataset(f'{project}.{dname}', exists_ok=True)
    job = bigquery_client.load_table_from_uri(
        source_uris=f'gs://{event["bucket"]}/{event["name"]}',
        destination=dataset.table(tname),
        job_config=bigquery.LoadJobConfig(
            autodetect=True,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE))
    job.result()
    print(f'loaded table {tname} into dataset {dname}')
