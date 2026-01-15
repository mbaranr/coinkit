import requests


def notify(webhook_url, message):
    response = requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )
    response.raise_for_status()