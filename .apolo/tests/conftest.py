import contextlib
import typing as t

import apolo_sdk
import pytest
import yarl


pytest_plugins = [
    "apolo_app_types_fixtures.apolo_clients",
]


@pytest.fixture
def apolo_client(setup_clients):
    apolo_sdk_client = setup_clients

    @contextlib.asynccontextmanager
    async def _open(uri: yarl.URL) -> t.AsyncIterator[bytes]:
        async def generator():
            if uri != yarl.URL("storage:.apps/n8n/n8n-app/config"):
                raise apolo_sdk.ResourceNotFound()
            payload = '{"encryptionKey": "some-encryption-key"}'
            for char in payload:
                yield char.encode()

        yield generator()

    apolo_sdk_client.storage.open = _open
    return apolo_sdk_client
