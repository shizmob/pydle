import asyncio
import pytest
import pytest_asyncio

import pydle


@pytest_asyncio.fixture
async def socket():
    async def on_connect(r, w):
        w.close()

    host = "localhost"
    port = 9999
    server = await asyncio.start_server(on_connect, host, port)

    yield host, port

    server.close()


@pytest.mark.asyncio
async def test_socket_connect(socket):
    host, port = socket
    client = pydle.Client("MyBot", realname="My Bot")
    await client.connect(host, port, tls=False)
