import time

import pytest
import pydle
from .fixtures import with_client, Mock

@with_client()
def test_client_same_nick(server, client):
    assert client.is_same_nick('WiZ', 'WiZ')
    assert not client.is_same_nick('WiZ', 'jilles')
    assert not client.is_same_nick('WiZ', 'wiz')

@with_client()
def test_client_same_channel(server, client):
    assert client.is_same_channel('#lobby', '#lobby')
    assert not client.is_same_channel('#lobby', '#support')
    assert not client.is_same_channel('#lobby', 'jilles')

@with_client()
def test_client_unknown(server, client):
    client.on_unknown = Mock()
    server.send('INSTALL', 'gentoo')
    assert client.on_unknown.called

@pytest.mark.slow
@with_client()
def test_client_timeout(server, client):
    client.on_data_error = Mock()

    time.sleep(pydle.client.PING_TIMEOUT + 1)
    assert client.on_data_error.called
