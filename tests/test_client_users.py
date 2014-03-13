import pydle
from .fixtures import with_client
from .mocks import Mock


@with_client()
def test_user_creation(server, client):
    client._create_user('WiZ')
    assert 'WiZ' in client.users
    assert client.users['WiZ']['nickname'] == 'WiZ'

@with_client()
def test_user_renaming(server, client):
    client._create_user('WiZ')
    client._rename_user('WiZ', 'jilles')

    assert 'WiZ' not in client.users
    assert 'jilles' in client.users
    assert client.users['jilles']['nickname'] == 'jilles'

@with_client()
def test_user_deletion(server, client):
    client._create_user('WiZ')
    client._destroy_user('WiZ')

    assert 'WiZ' not in client.users
