import pydle
from .fixtures import with_client


@with_client()
def test_client_same_channel(server, client):
    assert client.is_same_channel('#lobby', '#lobby')
    assert not client.is_same_channel('#lobby', '#support')
    assert not client.is_same_channel('#lobby', 'jilles')

@with_client()
def test_client_in_channel(server, client):
    client._create_channel('#lobby')
    assert client.in_channel('#lobby')

@with_client()
def test_client_is_channel(server, client):
    # Test always true...
    assert client.is_channel('#lobby')
    assert client.is_channel('WiZ')
    assert client.is_channel('irc.fbi.gov')

@with_client()
def test_channel_creation(server, client):
    client._create_channel('#pydle')
    assert '#pydle' in client.channels
    assert client.channels['#pydle'].users == set()

@with_client()
def test_channel_destruction(server, client):
    client._create_channel('#pydle')
    client._destroy_channel('#pydle')
    assert '#pydle' not in client.channels

@with_client()
def test_channel_user_destruction(server, client):
    client._create_channel('#pydle')
    client._create_user('WiZ')
    client.channels['#pydle'].users.add('WiZ')

    client._destroy_channel('#pydle')
    assert '#pydle' not in client.channels
    assert 'WiZ' not in client.users
