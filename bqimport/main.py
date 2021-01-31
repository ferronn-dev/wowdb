import json
import re
from google.cloud import bigquery

project = 'wow-ferronn-dev'
bigquery_client = bigquery.Client(project)

job_configs = {
    'json': lambda _: bigquery.LoadJobConfig(
        autodetect=True,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE),
    'csv': lambda event: bigquery.LoadJobConfig(
        allow_quoted_newlines=True,
        autodetect=False,
        schema=[
            bigquery.schema.SchemaField(name=header, field_type='STRING')
            for header in json.loads(event['metadata']['headers'])
        ],
        skip_leading_rows=1,
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE),
}

def bqimport(event, _):
    dname, tname, ext = re.match(r'([^/]+)/(.+)\.(.+)$', event['name']).groups()
    dataset = bigquery_client.create_dataset(f'{project}.{dname}', exists_ok=True)
    job = bigquery_client.load_table_from_uri(
        source_uris=f'gs://{event["bucket"]}/{event["name"]}',
        destination=dataset.table(tname),
        job_config=job_configs[ext](event))
    job.result()
    print(f'loaded table {tname} into dataset {dname}')
