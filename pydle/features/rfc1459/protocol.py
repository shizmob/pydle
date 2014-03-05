## protocol.py
# RFC1459 protocol constants.
import re
import collections
from pydle.client import Error


class ServerError(Error):
    pass


# While this *technically* is supposed to be 143, I've yet to see a server that actually uses those.
DEFAULT_PORT = 6667


## Limits.

CHANNEL_LIMITS_GROUPS = {
    '#': frozenset('#&'),
    '&': frozenset('#&')
}
CHANNEL_LIMITS = {
    frozenset('#&'): 10
}
LIST_LIMITS_GROUPS = {
    'b': frozenset('b')
}
LIST_LIMITS = {
    frozenset('b'): None
}
PARAMETER_LIMIT = 15
MESSAGE_LENGTH_LIMIT = 512
CHANNEL_LENGTH_LIMIT = 200
NICKNAME_LENGTH_LIMIT = 8
TOPIC_LENGTH_LIMIT = 450


## Defaults.

BEHAVIOUR_NO_PARAMETER = 'noparam'
BEHAVIOUR_PARAMETER = 'param'
BEHAVIOUR_PARAMETER_ON_SET = 'param_set'
BEHAVIOUR_LIST = 'list'

CHANNEL_MODES = { 'o', 'p', 's', 'i', 't', 'n', 'b', 'v', 'm', 'r', 'k', 'l' }
CHANNEL_MODES_BEHAVIOUR = {
    BEHAVIOUR_LIST: { 'b' },
    BEHAVIOUR_PARAMETER: { 'o', 'v' },
    BEHAVIOUR_PARAMETER_ON_SET: { 'k', 'l' },
    BEHAVIOUR_NO_PARAMETER: { 'p', 's', 'i', 't', 'n', 'm', 'r' }
}
CHANNEL_PREFIXES = { '#', '&' }
CASE_MAPPINGS = { 'ascii', 'rfc1459', 'strict-rfc1459' }
DEFAULT_CASE_MAPPING = 'rfc1459'
NICKNAME_PREFIXES = collections.OrderedDict([
    ('@', 'o'),
    ('+', 'v')
])
USER_MODES = { 'i', 'w', 's', 'o' }
# Maybe one day, user modes will have parameters...
USER_MODES_BEHAVIOUR = {
    BEHAVIOUR_NO_PARAMETER: { 'i', 'w', 's', 'o' }
}


## Message parsing.

LINE_SEPARATOR = '\r\n'
MINIMAL_LINE_SEPARATOR = '\n'

FORBIDDEN_CHARACTERS = { '\r', '\n', '\0' }
USER_SEPARATOR = '!'
HOST_SEPARATOR = '@'

PRIVATE_CHANNEL_SIGIL = '@'
SECRET_CHANNEL_SIGIL = '*'
PUBLIC_CHANNEL_SIGIL = '='

ARGUMENT_SEPARATOR = re.compile(' +', re.UNICODE)
COMMAND_PATTERN = re.compile('^([a-zA-Z]+|[0-9]+)$', re.UNICODE)
TRAILING_PREFIX = ':'
