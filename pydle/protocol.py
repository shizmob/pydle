## protocol.py
# IRC implementation-agnostic constants/helpers.
from abc import ABCMeta, abstractmethod

# While this *technically* is supposed to be 143, I've yet to see a server that actually uses those.
DEFAULT_PORT = 6667

DEFAULT_ENCODING = 'utf-8'
FALLBACK_ENCODING = 'iso-8859-1'

LINE_SEPARATOR = '\r\n'
MINIMAL_LINE_SEPARATOR = '\n'

## Errors.

class ProtocolViolation(Exception):
    """ An error that occurred while parsing or constructing an IRC message that violates the IRC protocol. """
    def __init__(self, msg, message):
        super().__init__(msg)
        self.irc_message = message


## Bases.

class Message:
    @classmethod
    @abstractmethod
    def parse(cls, line, encoding=DEFAULT_ENCODING):
        """ Parse data into IRC message. Return a Message instance or raise an error. """
        raise NotImplementedError()


    @abstractmethod
    def construct(self, force=False):
        """ Convert message into raw IRC command. If `force` is True, don't attempt to check message validity. """
        raise NotImplementedError()

    def __str__(self):
        return self.construct()