from datetime import datetime
from datetime import timedelta
import json
from google.cloud import bigquery
from google.cloud import pubsub_v1

GITPUBS = [
    { 'repo': repo, 'workflow': 'build.yml' }
    for repo in [
        'ferronnizer',
        'lib-classic-gear-planner',
        'olliverrstravels',
    ]
]

bigquery_client = bigquery.Client('wow-ferronn-dev')
pubsub_client = pubsub_v1.PublisherClient()
pubsub_topic = pubsub_client.topic_path('wow-ferronn-dev', 'gitpub')

def done(msg):
    print(msg)
    return msg

def poll(_):
    jobs = bigquery_client.list_jobs(
        all_users=True,
        state_filter='done',
        min_creation_time=datetime.utcnow() - timedelta(minutes=10))
    if not any([job.job_type == 'load' for job in jobs]):
        return done('no loads to report')
    futures = [
        pubsub_client.publish(
            pubsub_topic,
            json.dumps(data).encode('ascii'))
        for data in GITPUBS
    ]
    results = [f.result() for f in futures]
    return done(f'published {len(results)} messages')
