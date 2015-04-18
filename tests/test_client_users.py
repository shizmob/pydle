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
    assert client.users['WiZ'].nickname == 'WiZ'


@with_client()
def test_user_renaming(server, client):
    client._create_user('WiZ')
    client._rename_user('WiZ', 'jilles')

    assert 'WiZ' not in client.users
    assert 'jilles' in client.users
    assert client.users['jilles'].nickname == 'jilles'

@with_client()
def test_user_renaming_creation(server, client):
    client._rename_user('null', 'WiZ')

    assert 'WiZ' in client.users
    assert 'null' not in client.users


@with_client()
def test_user_renaming_channel_users(server, client):
    client._create_user('WiZ')
    client._create_channel('#lobby')
    client.channels['#lobby'].users.add('WiZ')

    client._rename_user('WiZ', 'jilles')
    assert 'WiZ' not in client.channels['#lobby'].users
    assert 'jilles' in client.channels['#lobby'].users


@with_client()
def test_user_deletion(server, client):
    client._create_user('WiZ')
    client._destroy_user('WiZ')

    assert 'WiZ' not in client.users

@with_client()
def test_user_channel_deletion(server, client):
    client._create_channel('#lobby')
    client._create_user('WiZ')
    client.channels['#lobby'].users.add('WiZ')

    client._destroy_user('WiZ', '#lobby')
    assert 'WiZ' not in client.users
    assert client.channels['#lobby'].users == set()

@with_client()
def test_user_channel_incomplete_deletion(server, client):
    client._create_channel('#lobby')
    client._create_channel('#foo')
    client._create_user('WiZ')
    client.channels['#lobby'].users.add('WiZ')
    client.channels['#foo'].users.add('WiZ')

    client._destroy_user('WiZ', '#lobby')
    assert 'WiZ' in client.users
    assert client.channels['#lobby'].users == set()


@with_client()
def test_user_get(server, client):
    client._get_user('WiZ')
    assert 'WiZ' in client.users


@with_client()
def test_user_mask_format(server, client):
    client._create_user('WiZ')
    wiz = client.users['WiZ']
    assert client._format_user_mask('WiZ') == 'WiZ!*@*'

    wiz.username = 'wiz'
    assert client._format_user_mask('WiZ') == 'WiZ!wiz@*'

    wiz.hostname = 'og.irc.developer'
    assert client._format_user_mask('WiZ') == 'WiZ!wiz@og.irc.developer'

    wiz.username = None
    assert client._format_user_mask('WiZ') == 'WiZ!*@og.irc.developer'
