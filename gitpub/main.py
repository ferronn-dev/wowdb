import requests
from google.cloud import secretmanager

secret_client = secretmanager.SecretManagerServiceClient()
secret = secret_client.access_secret_version(request={
    'name': 'projects/wow-ferronn-dev/secrets/github-build-trigger/versions/latest',
}).payload.data
print('retrieved secret')

def publish(event, _):
    root = 'https://api.github.com/repos'
    user = 'ferronn-dev'
    repo = event['repo']
    workflow = event['workflow']
    print(f'publishing to {repo}')
    req = requests.post(
        f'{root}/{user}/{repo}/actions/workflows/{workflow}/dispatches',
        headers={'Authorization': f'token {secret}'},
        data={'ref':'main'})
    req.raise_for_status()
    print(f'published to {repo}')
