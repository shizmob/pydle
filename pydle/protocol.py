## protocol.py
# IRC implementation-agnostic constants/helpers.
import re
from abc import abstractmethod

DEFAULT_ENCODING = 'utf-8'
FALLBACK_ENCODING = 'iso-8859-1'


## Errors.

class ProtocolViolation(Exception):
    """ An error that occurred while parsing or constructing an IRC message that violates the IRC protocol. """
    def __init__(self, msg, message):
        super().__init__(msg)
        self.irc_message = message


## Bases.

class Message:
    """ Abstract message class. Messages must inherit from this class. """
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

## Misc.

def identifierify(name):
    """ Clean up name so it works for a Python identifier. """
    name = name.lower()
    name = re.sub('[^a-z0-9]', '_', name)
    return name
