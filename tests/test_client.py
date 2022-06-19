import time
import pytest
from pytest import raises, mark
import pydle
from .fixtures import with_client
from .mocks import Mock

pydle.client.PING_TIMEOUT = 10


## Initialization.


@pytest.mark.asyncio
@with_client(invalid_kwarg=False)
def test_client_superfluous_arguments(server, client):
    assert client.logger.warning.called


## Connection.
@pytest.mark.asyncio
@with_client()
async def test_client_reconnect(server, client):
    await client.disconnect(expected=True)
    assert not client.connected

    await client.connect(reconnect=True)
    assert client.connected


@pytest.mark.asyncio
@mark.slow
@with_client()
async def test_client_unexpected_disconnect_reconnect(server, client):
    client._reconnect_delay = Mock(return_value=0)
    await client.disconnect(expected=False)
    assert client._reconnect_delay.called

    time.sleep(0.1)
    assert client.connected


@pytest.mark.asyncio
@with_client()
async def test_client_unexpected_reconnect_give_up(server, client):
    client.RECONNECT_ON_ERROR = False
    await client.disconnect(expected=False)
    assert not client.connected


@pytest.mark.asyncio
@mark.slow
@with_client()
async def test_client_unexpected_disconnect_reconnect_delay(server, client):
    client._reconnect_delay = Mock(return_value=1)
    await client.disconnect(expected=False)

    assert not client.connected
    time.sleep(1.1)
    assert client.connected


@pytest.mark.asyncio
@with_client()
def test_client_reconnect_delay_calculation(server, client):
    client.RECONNECT_DELAYED = False
    assert client._reconnect_delay() == 0

    client.RECONNECT_DELAYED = True
    for expected_delay in client.RECONNECT_DELAYS:
        delay = client._reconnect_delay()
        assert delay == expected_delay

        client._reconnect_attempts += 1

    assert client._reconnect_delay() == client.RECONNECT_DELAYS[-1]


@pytest.mark.asyncio
@with_client()
async def test_client_disconnect_on_connect(server, client):
    client.disconnect = Mock()

    await client.connect("mock://local", 1337)
    assert client.connected
    assert client.disconnect.called


@pytest.mark.asyncio
@with_client(connected=False)
async def test_client_connect_invalid_params(server, client):
    with raises(ValueError):
        await client.connect()
    with raises(ValueError):
        await client.connect(port=1337)


@pytest.mark.asyncio
@mark.slow
@with_client()
async def test_client_timeout(server, client):
    client.on_data_error = Mock()
    time.sleep(pydle.client.BasicClient.READ_TIMEOUT + 1)

    assert client.on_data_error.called
    assert isinstance(client.on_data_error.call_args[0][0], TimeoutError)


@pytest.mark.asyncio
@with_client(connected=False)
async def test_client_server_tag(server, client):
    assert client.server_tag is None

    await client.connect("Mock.local", 1337)
    assert client.server_tag == "mock"
    await client.disconnect()

    await client.connect("irc.mock.local", 1337)
    assert client.server_tag == "mock"
    await client.disconnect()

    await client.connect("mock", 1337)
    assert client.server_tag == "mock"
    await client.disconnect()

    await client.connect("127.0.0.1", 1337)
    assert client.server_tag == "127.0.0.1"

    client.network = "MockNet"
    assert client.server_tag == "mocknet"
    await client.disconnect()


## Messages.


@pytest.mark.asyncio
@with_client()
async def test_client_message(server, client):
    client.on_raw_install = Mock()
    await server.send("INSTALL", "gentoo")
    assert client.on_raw_install.called

    message = client.on_raw_install.call_args[0][0]
    assert isinstance(message, pydle.protocol.Message)
    assert message.command == "INSTALL"
    assert message.params == ("gentoo",)


@pytest.mark.asyncio
@with_client()
async def test_client_unknown(server, client):
    client.on_unknown = Mock()
    await server.send("INSTALL", "gentoo")
    assert client.on_unknown.called
