import base64
import json
import requests
from google.cloud import secretmanager

secret_client = secretmanager.SecretManagerServiceClient()
secret = secret_client.access_secret_version(request={
    'name': 'projects/wow-ferronn-dev/secrets/github-build-trigger/versions/latest',
}).payload.data
print('retrieved secret')

def publish(event, _):
    data = json.loads(base64.b64decode(event['data']))
    root = 'https://api.github.com/repos'
    user = 'ferronn-dev'
    repo = data['repo']
    workflow = data['workflow']
    print(f'publishing to {repo}')
    req = requests.post(
        f'{root}/{user}/{repo}/actions/workflows/{workflow}/dispatches',
        headers={'Authorization': f'token {secret}'},
        data={'ref':'main'})
    req.raise_for_status()
    print(f'published to {repo}')
