## ctcp.py
# Client-to-Client-Protocol (CTCP) support.
import pydle.protocol
from pydle.features import rfc1459
from pydle import client
__all__ = [ 'CTCPSupport' ]


CTCP_DELIMITER = '\x01'
CTCP_ESCAPE_CHAR = '\x16'


class CTCPSupport(rfc1459.RFC1459Support):
    """ Support for CTCP messages. """

    ## Callbacks.

    async def on_ctcp(self, by, target, what, contents):
        """
        Callback called when the user received a CTCP message.
        Client subclasses can override on_ctcp_<type> to be called when receiving a message of that specific CTCP type,
        in addition to this callback.
        """
        pass

    async def on_ctcp_reply(self, by, target, what, response):
        """
        Callback called when the user received a CTCP response.
        Client subclasses can override on_ctcp_<type>_reply to be called when receiving a reply of that specific CTCP type,
        in addition to this callback.
        """
        pass

    async def on_ctcp_version(self, by, target, contents):
        """ Built-in CTCP version as some networks seem to require it. """
        import pydle

        version = '{name} v{ver}'.format(name=pydle.__name__, ver=pydle.__version__)
        await self.ctcp_reply(by, 'VERSION', version)


    ## IRC API.

    async def ctcp(self, target, query, contents=None):
        """ Send a CTCP request to a target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise client.NotInChannel(target)

        await self.message(target, construct_ctcp(query, contents))

    async def ctcp_reply(self, target, query, response):
        """ Send a CTCP reply to a target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise client.NotInChannel(target)

        await self.notice(target, construct_ctcp(query, response))


    ## Handler overrides.

    async def on_raw_privmsg(self, message):
        """ Modify PRIVMSG to redirect CTCP messages. """
        nick, metadata = self._parse_user(message.source)
        target, msg = message.params

        if is_ctcp(msg):
            self._sync_user(nick, metadata)
            type, contents = parse_ctcp(msg)

            # Find dedicated handler if it exists.
            attr = 'on_ctcp_' + pydle.protocol.identifierify(type)
            if hasattr(self, attr):
                await getattr(self, attr)(nick, target, contents)
            # Invoke global handler.
            await self.on_ctcp(nick, target, type, contents)
        else:
            await super().on_raw_privmsg(message)


    async def on_raw_notice(self, message):
        """ Modify NOTICE to redirect CTCP messages. """
        nick, metadata = self._parse_user(message.source)
        target, msg = message.params

        if is_ctcp(msg):
            self._sync_user(nick, metadata)
            _type, response = parse_ctcp(msg)

            # Find dedicated handler if it exists.
            attr = 'on_ctcp_' + pydle.protocol.identifierify(_type) + '_reply'
            if hasattr(self, attr):
                await getattr(self, attr)(nick, target, response)
            # Invoke global handler.
            await self.on_ctcp_reply(nick, target, _type, response)
        else:
            await super().on_raw_notice(message)


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

def parse_ctcp(query):
    """ Strip and de-quote CTCP messages. """
    query = query.strip(CTCP_DELIMITER)
    query = query.replace(CTCP_ESCAPE_CHAR + '0', '\0')
    query = query.replace(CTCP_ESCAPE_CHAR + 'n', '\n')
    query = query.replace(CTCP_ESCAPE_CHAR + 'r', '\r')
    query = query.replace(CTCP_ESCAPE_CHAR + CTCP_ESCAPE_CHAR, CTCP_ESCAPE_CHAR)
    if ' ' in query:
        return query.split(' ', 1)
    return query, None
