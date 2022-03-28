import time
import datetime

import pytest

import pydle

from pytest import mark
from .fixtures import with_client
from .mocks import Mock, MockEventLoop, MockConnection


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
    await client.connect("mock://local", 1337, eventloop=MockEventLoop())

    assert client.connected
    assert client.on_connect.called

    client.disconnect()
    assert not client.connected


@pytest.mark.asyncio
@mark.meta
@with_client()
def test_mock_client_send(server, client):
    client.raw("benis")
    assert server.receiveddata("benis")
    client.rawmsg("INSTALL", "Gentoo")
    assert server.received("INSTALL", "Gentoo")


@pytest.mark.asyncio
@mark.meta
@with_client(pydle.features.RFC1459Support)
def test_mock_client_receive(server, client):
    client.on_raw = Mock()
    server.send("PING", "test")
    assert client.on_raw.called

    message = client.on_raw.call_args[0][0]
    assert isinstance(message, pydle.protocol.Message)
    assert message.source is None
    assert message.command == "PING"
    assert message.params == ("test",)


## Connection.


@mark.meta
def test_mock_connection_connect():
    serv = Mock()
    conn = MockConnection("mock.local", port=1337, mock_server=serv)

    conn.connect()
    assert conn.connected
    assert serv.connection is conn


@mark.meta
def test_mock_connection_disconnect():
    serv = Mock()
    conn = MockConnection("mock.local", port=1337, mock_server=serv)

    conn.connect()
    conn.disconnect()
    assert not conn.connected


## Event loop.


@mark.meta
def test_mock_eventloop_schedule():
    ev = MockEventLoop()
    passed = Passed()

    ev.schedule(lambda: passed.set())
    assert passed

    ev.stop()


@mark.meta
@mark.slow
def test_mock_eventloop_schedule_in():
    ev = MockEventLoop()
    passed = Passed()

    ev.schedule_in(1, lambda: passed.set())
    time.sleep(1.1)
    assert passed

    ev.stop()


@mark.meta
@mark.slow
def test_mock_eventloop_schedule_in_timedelta():
    ev = MockEventLoop()
    passed = Passed()

    ev.schedule_in(datetime.timedelta(seconds=1), lambda: passed.set())
    time.sleep(1.1)
    assert passed


@mark.meta
@mark.slow
def test_mock_eventloop_schedule_periodically():
    ev = MockEventLoop()
    passed = Passed()

    ev.schedule_periodically(1, lambda: passed.set())
    time.sleep(1.1)
    assert passed

    passed.reset()
    time.sleep(1)
    assert passed

    ev.stop()


@mark.meta
@mark.slow
def test_mock_eventloop_unschedule_in():
    ev = MockEventLoop()
    passed = Passed()

    handle = ev.schedule_in(1, lambda: passed.set())
    ev.unschedule(handle)

    time.sleep(1.1)
    assert not passed


@mark.meta
@mark.slow
def test_mock_eventloop_unschedule_periodically():
    ev = MockEventLoop()
    passed = Passed()

    handle = ev.schedule_periodically(1, lambda: passed.set())
    ev.unschedule(handle)

    time.sleep(1.1)
    assert not passed


@mark.meta
@mark.slow
def test_mock_eventloop_unschedule_periodically_after():
    ev = MockEventLoop()
    passed = Passed()

    handle = ev.schedule_periodically(1, lambda: passed.set())

    time.sleep(1.1)
    assert passed

    passed.reset()
    ev.unschedule(handle)
    time.sleep(1.0)
    assert not passed
