import pytest
import pydle
from .fixtures import with_client


@pytest.mark.asyncio
@with_client()
def test_client_same_nick(server, client):
    assert client.is_same_nick("WiZ", "WiZ")
    assert not client.is_same_nick("WiZ", "jilles")
    assert not client.is_same_nick("WiZ", "wiz")


@pytest.mark.asyncio
@with_client()
async def test_user_creation(server, client):
    await client._create_user("WiZ")
    assert "WiZ" in client.users
    assert client.users["WiZ"]["nickname"] == "WiZ"


@pytest.mark.asyncio
@with_client()
async def test_user_invalid_creation(server, client):
    await client._create_user("irc.fbi.gov")
    assert "irc.fbi.gov" not in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_renaming(server, client):
    await client._create_user("WiZ")
    await client._rename_user("WiZ", "jilles")

    assert "WiZ" not in client.users
    assert "jilles" in client.users
    assert client.users["jilles"]["nickname"] == "jilles"


@pytest.mark.asyncio
@with_client()
async def test_user_renaming_creation(server, client):
    await client._rename_user("null", "WiZ")

    assert "WiZ" in client.users
    assert "null" not in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_renaming_invalid_creation(server, client):
    await client._rename_user("null", "irc.fbi.gov")

    assert "irc.fbi.gov" not in client.users
    assert "null" not in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_renaming_channel_users(server, client):
    await client._create_user("WiZ")
    client._create_channel("#lobby")
    client.channels["#lobby"]["users"].add("WiZ")

    await client._rename_user("WiZ", "jilles")
    assert "WiZ" not in client.channels["#lobby"]["users"]
    assert "jilles" in client.channels["#lobby"]["users"]


@pytest.mark.asyncio
@with_client()
async def test_user_deletion(server, client):
    await client._create_user("WiZ")
    client._destroy_user("WiZ")

    assert "WiZ" not in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_channel_deletion(server, client):
    client._create_channel("#lobby")
    await client._create_user("WiZ")
    client.channels["#lobby"]["users"].add("WiZ")

    client._destroy_user("WiZ", "#lobby")
    assert "WiZ" not in client.users
    assert client.channels["#lobby"]["users"] == set()


@pytest.mark.asyncio
@with_client()
async def test_user_channel_incomplete_deletion(server, client):
    client._create_channel("#lobby")
    client._create_channel("#foo")
    await client._create_user("WiZ")
    client.channels["#lobby"]["users"].add("WiZ")
    client.channels["#foo"]["users"].add("WiZ")

    client._destroy_user("WiZ", "#lobby")
    assert "WiZ" in client.users
    assert client.channels["#lobby"]["users"] == set()


@pytest.mark.asyncio
@with_client()
async def test_user_synchronization(server, client):
    await client._create_user("WiZ")
    await client._sync_user("WiZ", {"hostname": "og.irc.developer"})

    assert client.users["WiZ"]["hostname"] == "og.irc.developer"


@pytest.mark.asyncio
@with_client()
async def test_user_synchronization_creation(server, client):
    await client._sync_user("WiZ", {})
    assert "WiZ" in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_invalid_synchronization(server, client):
    await client._sync_user("irc.fbi.gov", {})
    assert "irc.fbi.gov" not in client.users


@pytest.mark.asyncio
@with_client()
async def test_user_mask_format(server, client):
    await client._create_user("WiZ")
    assert client._format_user_mask("WiZ") == "WiZ!*@*"

    await client._sync_user("WiZ", {"username": "wiz"})
    assert client._format_user_mask("WiZ") == "WiZ!wiz@*"

    await client._sync_user("WiZ", {"hostname": "og.irc.developer"})
    assert client._format_user_mask("WiZ") == "WiZ!wiz@og.irc.developer"

    await client._sync_user("WiZ", {"username": None})
    assert client._format_user_mask("WiZ") == "WiZ!*@og.irc.developer"
