import temporalio.converter
from temporalio.client import Client
from temporalio.contrib.pydantic import PydanticPayloadConverter

from nomad.actions._codec import EncryptionCodec
from nomad.config import config
from nomad.config.models.config import ModeEnum


async def get_client() -> Client:
    host = f'{config.temporal.host}:{config.temporal.port}'
    data_converter = temporalio.converter.DataConverter(
        payload_converter_class=PydanticPayloadConverter,
        payload_codec=None
        # Disable encryption in dev mode
        if config.services.mode == ModeEnum.DEVELOPMENT
        else EncryptionCodec(),
    )
    client = await Client.connect(
        host,
        namespace=config.temporal.namespace,
        data_converter=data_converter,
    )
    return client
