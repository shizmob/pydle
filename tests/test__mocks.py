import pytest
from pytest import mark
import pydle
from .fixtures import with_client
from .mocks import Mock, MockConnection


class Passed:
    def __init__(self):
        self._passed = False

    def __bool__(self):
        return self._passed

    def set(self):
        self._passed = True

    def reset(self):
        self._passed = False


## Client.


@pytest.mark.asyncio
@mark.meta
@with_client(connected=False)
async def test_mock_client_connect(server, client):
    assert not client.connected
    client.on_connect = Mock()
    await client.connect("mock://local", 1337)

    assert client.connected
    assert client.on_connect.called

    client.disconnect()
    assert not client.connected


@pytest.mark.asyncio
@mark.meta
@with_client()
async def test_mock_client_send(server, client):
    await client.raw("benis")
    assert server.receiveddata("benis")
    await client.rawmsg("INSTALL", "Gentoo")
    assert server.received("INSTALL", "Gentoo")


@pytest.mark.asyncio
@mark.meta
@with_client(pydle.features.RFC1459Support)
async def test_mock_client_receive(server, client):
    client.on_raw = Mock()
    server.send("PING", "test")
    assert client.on_raw.called

    message = client.on_raw.call_args[0][0]
    assert isinstance(message, pydle.protocol.Message)
    assert message.source is None
    assert message.command == "PING"
    assert message.params == ("test",)


## Connection.


@pytest.mark.asyncio
@mark.meta
async def test_mock_connection_connect():
    serv = Mock()
    conn = MockConnection("mock.local", port=1337, mock_server=serv)

    await conn.connect()
    assert conn.connected
    assert serv.connection is conn


@pytest.mark.asyncio
@mark.meta
async def test_mock_connection_disconnect():
    serv = Mock()
    conn = MockConnection("mock.local", port=1337, mock_server=serv)

    await conn.connect()
    await conn.disconnect()
    assert not conn.connected
