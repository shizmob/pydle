## ctcp.py
# Client-to-Client-Protocol (CTCP) support.
from .. import client
from .. import protocol

__all__ = [ 'CTCPSupport' ]


CTCP_DELIMITER = '\x01'
CTCP_ESCAPE_CHAR = '\x16'


class CTCPSupport(client.BasicClient):
    """ Support for CTCP messages. """

    ## Callbacks.

    def on_ctcp(self, by, target, what):
        pass

    def on_ctcp_reply(self, by, target, what, response):
        pass

    def on_ctcp_version(self, by, target):
        """ Built-in CTCP version as some networks seem to require it. """
        import pydle

        version = '{name} v{ver}'.format(name=pydle.__name__, ver=pydle.__version__)
        self.ctcp_reply(by, 'VERSION', version)


    ## IRC API.

    def ctcp(self, target, query):
        """ CTCP request from target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise client.NotInChannel('Not in channel {}'.format(target))

        self.message(target, construct_ctcp(query))

    def ctcp_reply(self, target, query, response):
        """ CTCP reply to target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise client.NotInChannel('Not in channel {}'.format(target))

        self.notice(target, construct_ctcp(query, response))


    ## Handler overrides.

    def on_raw_privmsg(self, source, params):
        """ Modify PRIVMSG to redirect CTCP messages. """
        nick, user, host = protocol.parse_user(source)
        target, message = params

        if is_ctcp(message):
            if nick in self.users:
                self._sync_user(nick, user, host)
            type = parse_ctcp_query(message)

            # Find dedicated handler if it exists.
            attr = 'on_ctcp_' + type.lower()
            if hasattr(self, attr):
                getattr(self, attr)(nick, target)
            else:
                # Invoke global handler.
                self.on_ctcp(nick, target, type)
        else:
            super().on_raw_privmsg(source, params)

    def on_raw_notice(self, source, params):
        """ Modify NOTICE to redirect CTCP messages. """
        nick, user, host = protocol.parse_user(source)
        target, message = params

        if is_ctcp(message):
            if nick in self.users:
                self._sync_user(nick, user, host)
            type, response = parse_ctcp_response(message)

            # Find dedicated handler if it exists.
            attr = 'on_ctcp_' + type.lower() + '_reply'
            if hasattr(self, attr):
                getattr(self, attr)(user, target, response)
            else:
                # Invoke global handler.
                self.on_ctcp_reply(user, target, type, response)
        else:
            super().on_raw_notice(source, params)


## Helpers.

def is_ctcp(message):
    """ Check if message follows the CTCP format. """
    return message.startswith(CTCP_DELIMITER) and message.endswith(CTCP_DELIMITER)

def construct_ctcp(*parts):
    """ Construct CTCP message. """
    message = ' '.join(parts)
    message = message.replace('\0', CTCP_ESCAPE_CHAR + '0')
    message = message.replace('\n', CTCP_ESCAPE_CHAR + 'n')
    message = message.replace('\r', CTCP_ESCAPE_CHAR + 'r')
    message = message.replace(CTCP_ESCAPE_CHAR, CTCP_ESCAPE_CHAR + CTCP_ESCAPE_CHAR)
    return CTCP_DELIMITER + message + CTCP_DELIMITER

def parse_ctcp_query(query):
    """ Strip and de-quote CTCP messages. """
    query = query.strip(CTCP_DELIMITER)
    query = query.replace(CTCP_ESCAPE_CHAR + '0', '\0')
    query = query.replace(CTCP_ESCAPE_CHAR + 'n', '\n')
    query = query.replace(CTCP_ESCAPE_CHAR + 'r', '\r')
    query = query.replace(CTCP_ESCAPE_CHAR + CTCP_ESCAPE_CHAR, CTCP_ESCAPE_CHAR)
    return query

def parse_ctcp_response(response):
    """ Strip and de-quote CTCP response. """
    response = parse_ctcp_query(response)
    return response.split(' ', 1)
