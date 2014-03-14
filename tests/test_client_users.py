import pydle
from .fixtures import with_client


@with_client()
def test_client_same_nick(server, client):
    assert client.is_same_nick('WiZ', 'WiZ')
    assert not client.is_same_nick('WiZ', 'jilles')
    assert not client.is_same_nick('WiZ', 'wiz')

@with_client()
def test_user_creation(server, client):
    client._create_user('WiZ')
    assert 'WiZ' in client.users
    assert client.users['WiZ']['nickname'] == 'WiZ'

@with_client()
def test_user_invalid_creation(server, client):
    client._create_user('irc.fbi.gov')
    assert 'irc.fbi.gov' not in client.users

@with_client()
def test_user_renaming(server, client):
    client._create_user('WiZ')
    client._rename_user('WiZ', 'jilles')

    assert 'WiZ' not in client.users
    assert 'jilles' in client.users
    assert client.users['jilles']['nickname'] == 'jilles'

@with_client()
def test_user_renaming_creation(server, client):
    client._rename_user('null', 'WiZ')

    assert 'WiZ' in client.users
    assert 'null' not in client.users

@with_client()
def test_user_deletion(server, client):
    client._create_user('WiZ')
    client._destroy_user('WiZ')

    assert 'WiZ' not in client.users

@with_client()
def test_user_synchronization(server, client):
    client._create_user('WiZ')
    client._sync_user('WiZ', { 'hostname': 'og.irc.developer' })

    assert client.users['WiZ']['hostname'] == 'og.irc.developer'

@with_client()
def test_user_synchronization_creation(server, client):
    client._sync_user('WiZ', {})
    assert 'WiZ' in client.users

@with_client()
def test_user_invalid_synchronization(server, client):
    client._sync_user('irc.fbi.gov', {})
    assert 'irc.fbi.gov' not in client.users
