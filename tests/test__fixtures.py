import pytest
from pytest import mark
import pydle
from .fixtures import with_client
from .mocks import MockClient, MockServer, MockConnection


@pytest.mark.asyncio
@mark.meta
@with_client(connected=False)
def test_fixtures_with_client(server, client):
    assert isinstance(server, MockServer)
    assert isinstance(client, MockClient)
    assert (
        client.__class__.__mro__[1] is MockClient
    ), "MockClient should be first in method resolution order"

    assert not client.connected


@pytest.mark.asyncio
@mark.meta
@with_client(pydle.features.RFC1459Support, connected=False)
def test_fixtures_with_client_features(server, client):
    assert isinstance(client, MockClient)
    assert (
        client.__class__.__mro__[1] is MockClient
    ), "MockClient should be first in method resolution order"
    assert isinstance(client, pydle.features.RFC1459Support)


@pytest.mark.asyncio
@mark.meta
@with_client(username="test_runner")
def test_fixtures_with_client_options(server, client):
    assert client.username == "test_runner"


@pytest.mark.asyncio
@mark.meta
@with_client()
async def test_fixtures_with_client_connected(server, client):
    assert client.connected
    assert isinstance(client.eventloop)
    assert isinstance(client.connection, MockConnection)
    assert isinstance(client.connection.eventloop)
    assert client.eventloop is client.connection.eventloop
