import pytest

from nomad.actions.client import get_client


@pytest.mark.skip(reason='CI cannot connect for some reason.')
@pytest.mark.asyncio
async def test_get_client():
    client = await get_client()
    assert client is not None
