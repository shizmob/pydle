import pytest

from pydle.features import ircv3

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
                rb"@+example=raw+:=,escaped\:\s\\ :irc.example.com NOTICE #channel :Message",
                {"+example": """raw+:=,escaped; \\"""}
        ),
        (
                rb"@+example=\foo\bar :irc.example.com NOTICE #channel :Message",
                {"+example": "foobar"}
        ),
    ]
)
def test_tagged_message_escape_sequences(payload, expected):
    message = ircv3.tags.TaggedMessage.parse(payload)

    assert message.tags == expected
