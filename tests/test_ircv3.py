import pytest

from pydle.features import ircv3

pytestmark = [pytest.mark.unit, pytest.mark.ircv3]


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
        (
                rb'@msgid=796~1602221579~51;account=user123 :user123!user123@((ip) PRIVMSG #user123 :ping',
                {'msgid': '796~1602221579~51', 'account': 'user123'}
        ),
        (
                rb'@inspircd.org/service;inspircd.org/bot :ChanServ!services@services.(domain) MODE #user123 +qo user123 :user123',
                {"inspircd.org/service": True, r"inspircd.org/bot": True}

        )
    ]
)
def test_tagged_message_escape_sequences(payload, expected):
    message = ircv3.tags.TaggedMessage.parse(payload)

    assert message.tags == expected
