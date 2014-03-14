import pydle
from .fixtures import with_client


@with_client()
def test_client_same_channel(server, client):
    assert client.is_same_channel('#lobby', '#lobby')
    assert not client.is_same_channel('#lobby', '#support')
    assert not client.is_same_channel('#lobby', 'jilles')

@with_client()
def test_channel_creation(server, client):
    client._create_channel('#pydle')
    assert '#pydle' in client.channels
    assert client.channels['#pydle']['users'] == set()

@with_client()
def test_channel_destruction(server, client):
    client._create_channel('#pydle')
    client._destroy_channel('#pydle')
    assert '#pydle' not in client.channels
