import pydle

from pytest import mark
from .fixtures import with_client
from .mocks import MockClient, MockServer, MockConnection, MockEventLoop


@mark.meta
@with_client(connected=False)
def test_fixtures_with_client(server, client):
    assert isinstance(server, MockServer)
    assert isinstance(client, MockClient)
    assert client.__class__.__mro__[1] is MockClient, 'MockClient should be first in method resolution order'

    assert not client.connected

@mark.meta
@with_client(pydle.features.RFC1459Support, connected=False)
def test_fixtures_with_client_features(server, client):
    assert isinstance(client, MockClient)
    assert client.__class__.__mro__[1] is MockClient, 'MockClient should be first in method resolution order'
    assert isinstance(client, pydle.features.RFC1459Support)

@mark.meta
@with_client(username='test_runner')
def test_fixtures_with_client_options(server, client):
    assert client.username == 'test_runner'

@mark.meta
@with_client()
def test_fixtures_with_client_connected(server, client):
    assert client.connected
    assert isinstance(client.eventloop, MockEventLoop)
    assert isinstance(client.connection, MockConnection)
    assert isinstance(client.connection.eventloop, MockEventLoop)
    assert client.eventloop is client.connection.eventloop
