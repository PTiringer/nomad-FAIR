from temporalio.client import Client

from nomad.config import config


async def get_client() -> Client:
    host = f'{config.temporal.host}:{config.temporal.port}'
    client = await Client.connect(
        host,
        namespace=config.temporal.namespace,
    )
    return client
