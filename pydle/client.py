## client.py
# Basic IRC client implementation.
import time
import datetime
import itertools
import logging

from . import async
from . import connection
from . import protocol

__all__ = [ 'Error', 'AlreadyInChannel', 'NotInChannel', 'BasicClient' ]
PING_TIMEOUT = 300
DEFAULT_NICKNAME = '<unregistered>'


class Error(Exception):
    """ Base class for all pydle errors. """
    pass

class NotInChannel(Error):
    def __init__(self, channel):
        super().__init__('Not in channel: {}'.format(channel))
        self.channel = channel

class AlreadyInChannel(Error):
    def __init__(self, channel):
        super().__init__('Already in channel: {}'.format(channel))
        self.channel = channel


class BasicClient:
    """
    Base IRC client class.
    This class on its own is not complete: in order to be able to run properly, _has_message, _parse_message and _create_message have to be overloaded.
    """
    RECONNECT_ON_ERROR = True
    RECONNECT_MAX_ATTEMPTS = 3
    RECONNECT_DELAYED = True
    RECONNECT_DELAYS = [0, 5, 10, 30, 120, 600]

    def __init__(self, nickname, fallback_nicknames=[], username=None, realname=None, **kwargs):
        """ Create a client. """
        self._nicknames = [nickname] + fallback_nicknames
        self.username = username or nickname.lower()
        self.realname = realname or nickname
        self.eventloop = None
        self.own_eventloop = True
        self._reset_connection_attributes()
        self._reset_attributes()

        if kwargs:
            self.logger.warning('Unused arguments: %s', ', '.join(kwargs.keys()))

    def _reset_attributes(self):
        """ Reset attributes. """
        # Record-keeping.
        self.channels = {}
        self.users = {}

        # Low-level data stuff.
        self._receive_buffer = b''
        self._pending = {}
        self._handler_top_level = False
        self._ping_checker_handle = None

        # Misc.
        self.logger = logging.getLogger(__name__)

        # Public connection attributes.
        self.nickname = DEFAULT_NICKNAME
        self.network = None

    def _reset_connection_attributes(self):
        """ Reset connection attributes. """
        self.connection = None
        self.encoding = None
        self._autojoin_channels = []
        self._reconnect_attempts = 0


    ## Connection.

    def connect(self, hostname=None, port=None, reconnect=False, eventloop=None, **kwargs):
        """ Connect to IRC server. """
        if (not hostname or not port) and not reconnect:
            raise ValueError('Have to specify hostname and port if not reconnecting.')

        # Disconnect from current connection.
        if self.connected:
            self.disconnect(expected=True)

        # Set event loop.
        if eventloop:
            self.eventloop = eventloop
        elif not self.eventloop:
            self.eventloop = async.EventLoop()
        self.own_eventloop = not eventloop

        # Reset attributes and connect.
        if not reconnect:
            self._reset_connection_attributes()
        self._connect(hostname=hostname, port=port, reconnect=reconnect, **kwargs)

        # Set logger name.
        if self.server_tag:
            self.logger = logging.getLogger(self.__class__.__name__ + ':' + self.server_tag)

    def disconnect(self, expected=True):
        """ Disconnect from server. """
        if self.connected:
            # Unschedule ping checker.
            self.eventloop.unschedule(self._ping_checker_handle)
            # Schedule disconnect.
            self.eventloop.schedule(self._disconnect, expected)

    def _disconnect(self, expected):
        # Shutdown connection.
        if self.connection.handles('read', self.on_data):
            self.connection.off('read', self.on_data)
        if self.connection.handles('error', self.on_data_error):
            self.connection.off('error', self.on_data_error)
        self.connection.disconnect()

        # Callback.
        self.on_disconnect(expected)

        # Shut down event loop.
        if expected and self.own_eventloop:
            self.connection.stop()

        # Reset any attributes.
        self._reset_attributes()

    def _connect(self, hostname, port, reconnect=False, channels=[], encoding=protocol.DEFAULT_ENCODING, source_address=None):
        """ Connect to IRC host. """
        # Create connection if we can't reuse it.
        if not reconnect or not self.connection:
            self._autojoin_channels = channels
            self.connection = connection.Connection(hostname, port, source_address=source_address, eventloop=self.eventloop)
            self.encoding = encoding

        # Connect.
        self.connection.connect()
        # Add handlers.
        self.connection.on('read', self.on_data)
        self.connection.on('error', self.on_data_error)

    def _reconnect_delay(self):
        """ Calculate reconnection delay. """
        if self.RECONNECT_ON_ERROR and self.RECONNECT_DELAYED:
            if self._reconnect_attempts >= len(self.RECONNECT_DELAYS):
                return self.RECONNECT_DELAYS[-1]
            else:
                return self.RECONNECT_DELAYS[self._reconnect_attempts]
        else:
            return 0

    def _perform_ping_timeout(self):
        """ Handle timeout gracefully. """
        error = TimeoutError('Ping timeout: no data received from server in {timeout} seconds.'.format(timeout=PING_TIMEOUT))
        self.on_data_error(error)


    ## Internal database management.

    def _create_channel(self, channel):
        self.channels[channel] = {
            'users': set(),
        }

    def _destroy_channel(self, channel):
        # Copy set to prevent a runtime error when destroying the user.
        for user in set(self.channels[channel]['users']):
            self._destroy_user(user, channel)
        del self.channels[channel]


    def _create_user(self, nickname):
        # Servers are NOT users.
        if not nickname or '.' in nickname:
            return

        self.users[nickname] = {
            'nickname': nickname,
            'username': None,
            'realname': None,
            'hostname': None
        }

    def _sync_user(self, nick, metadata):
        # Create user in database.
        if nick not in self.users:
            self._create_user(nick)
            if nick not in self.users:
                return

        self.users[nick].update(metadata)

    def _rename_user(self, user, new):
        if user in self.users:
            self.users[new] = self.users[user]
            self.users[new]['nickname'] = new
            del self.users[user]
        else:
            self._create_user(new)
            if new not in self.users:
                return

        for ch in self.channels.values():
            # Rename user in channel list.
            if user in ch['users']:
                ch['users'].discard(user)
                ch['users'].add(new)

    def _destroy_user(self, nickname, channel=None):
        if channel:
            channels = [ self.channels[channel] ]
        else:
            channels = self.channels.values()

        for ch in channels:
            # Remove from nicklist.
            ch['users'].discard(nickname)

        # If we're not in any common channels with the user anymore, we have no reliable way to keep their info up-to-date.
        # Remove the user.
        if not channel or not any(nickname in ch['users'] for ch in self.channels.values()):
            del self.users[nickname]

    def _parse_user(self, data):
        """ Parse user and return nickname, metadata tuple. """
        raise NotImplementedError()

    def _format_user_mask(self, nickname):
        user = self.users.get(nickname, { "nickname": nickname, "username": "*", "hostname": "*" })
        return self._format_host_mask(user['nickname'], user['username'] or '*', user['hostname'] or '*')

    def _format_host_mask(self, nick, user, host):
        return '{n}!{u}@{h}'.format(n=nick, u=user, h=host)


    ## IRC helpers.

    def is_channel(self, chan):
        """ Check if given argument is a channel name or not. """
        return True

    def in_channel(self, channel):
        """ Check if we are currently in the given channel. """
        return channel in self.channels.keys()

    def is_same_nick(self, left, right):
        """ Check if given nicknames are equal. """
        return left == right

    def is_same_channel(self, left, right):
        """ Check if given channel names are equal. """
        return left == right


    ## IRC attributes.

    @property
    def connected(self):
        """ Whether or not we are connected. """
        return self.connection and self.connection.connected

    @property
    def server_tag(self):
        if self.connected and self.connection.hostname:
            if self.network:
                tag = self.network.lower()
            else:
                tag = self.connection.hostname.lower()

                # Remove hostname prefix.
                if tag.startswith('irc.'):
                    tag = tag[4:]

                # Check if host is either an FQDN or IPv4.
                if '.' in tag:
                    # Attempt to cut off TLD.
                    host, suffix = tag.rsplit('.', 1)

                    # Make sure we aren't cutting off the last octet of an IPv4.
                    try:
                        int(suffix)
                    except ValueError:
                        tag = host

            return tag
        else:
            return None


    ## IRC API.

    def raw(self, message):
        """ Send raw command. """
        self._send(message)

    def rawmsg(self, command, *args, **kwargs):
        """ Send raw message. """
        message = str(self._create_message(command, *args, **kwargs))
        self._send(message)


    ## Overloadable callbacks.

    def on_connect(self):
        """ Callback called when the client has connected successfully. """
        # Reset reconnect attempts.
        self._reconnect_attempts = 0

    def on_disconnect(self, expected):
        if not expected:
            # Unexpected disconnect. Reconnect?
            if self.RECONNECT_ON_ERROR and (self.RECONNECT_MAX_ATTEMPTS is None or self._reconnect_attempts < self.RECONNECT_MAX_ATTEMPTS):
                # Calculate reconnect delay.
                delay = self._reconnect_delay()
                self._reconnect_attempts += 1

                if delay > 0:
                    self.logger.error('Unexpected disconnect. Attempting to reconnect within %s seconds.', delay)
                else:
                    self.logger.error('Unexpected disconnect. Attempting to reconnect.')

                # Wait and reconnect.
                self.eventloop.schedule_in(delay, self.connect, reconnect=True)
            else:
                self.logger.error('Unexpected disconnect. Giving up.')


    ## Message dispatch.

    def _has_message(self):
        """ Whether or not we have messages available for processing. """
        raise NotImplementedError()

    def _create_message(self, command, *params, **kwargs):
        raise NotImplementedError()

    def _parse_message(self):
        raise NotImplementedError()

    def _send(self, input):
        if not isinstance(input, (bytes, str)):
            input = str(input)
        if isinstance(input, str):
            input = input.encode(self.encoding)

        self.logger.debug('>> %s', input.decode(self.encoding))
        self.connection.send(input)

    def handle_forever(self):
        """ Handle data forever. """
        self.connection.run_forever()


    ## Raw message handlers.

    def on_data(self, data):
        """ Handle received data. """
        self._receive_buffer += data
        
        # Schedule new timeout event.
        self.eventloop.unschedule(self._ping_checker_handle)
        self._ping_checker_handle = self.eventloop.schedule_in(PING_TIMEOUT, self._perform_ping_timeout)

        while self._has_message():
            message = self._parse_message()
            self.on_raw(message)

    def on_data_error(self, exception):
        """ Handle error. """
        self.logger.error('Encountered error on socket.', exc_info=(type(exception), exception, None))
        self.disconnect(expected=False)

    def on_raw(self, message):
        """ Handle a single message. """
        self.logger.debug('<< %s', message._raw)
        if not message._valid:
            self.logger.warning('Encountered strictly invalid IRC message from server: %s', message._raw)

        if isinstance(message.command, int):
            cmd = str(message.command).zfill(3)
        else:
            cmd = message.command

        # Invoke dispatcher, if we have one.
        method = 'on_raw_' + cmd.lower()
        try:
            # Set _top_level so __getattr__() can decide whether to return on_unknown or _ignored for unknown handlers.
            # The reason for this is that features can always call super().on_raw_* safely and thus don't need to care for other features,
            # while unknown messages for which no handlers exist at all are still logged.
            self._handler_top_level = True
            handler = getattr(self, method)
            self._handler_top_level = False

            self.eventloop.schedule(handler, message)
        except:
            self.logger.exception('Failed to execute %s handler.', method)

    def on_unknown(self, message):
        """ Unknown command. """
        self.logger.warning('Unknown command: [%s] %s %s', message.source, message.command, message.params)

    def _ignored(self, message):
        """ Ignore message. """
        pass

    def __getattr__(self, attr):
        """ Return on_unknown or _ignored for unknown handlers, depending on the invocation type. """
        # Is this a raw handler?
        if attr.startswith('on_raw_'):
            # Are we in on_raw() trying to find any message handler?
            if self._handler_top_level:
                # In that case, return the method that logs and possibly acts on unknown messages.
                return self.on_unknown
            # Are we in an existing handler calling super()?
            else:
                # Just ignore it, then.
                return self._ignored

        # This isn't a handler, just raise an error.
        raise AttributeError(attr)


class ClientPool:
    """ A pool of clients that are ran and handled in parallel. """

    def __init__(self, clients=None, eventloop=None):
        if not eventloop:
            self.eventloop = async.EventLoop()
        else:
            self.eventloop = eventloop
        if not clients:
            self.clients = set()
        else:
            self.clients = set(clients)

    def add(self, client):
        """ Add client to pool. """
        self.clients.add(client)

    def remove(self, client):
        """ Remove client from pool. """
        self.clients.remove(client)

    def __contains__(self, item):
        return item in self.clients


    ## High-level.

    def connect(self, client, *args, eventloop=None, **kwargs):
        """
        Add client to pool and connect it using the given argument.
        Refer to the connect() method of the added client for details on parameters.
        """
        if client not in self:
            self.add(client)
        client.connect(*args, eventloop=self.eventloop, **kwargs)

    def disconnect(self, client, *args, **kwargs):
        """
        Disconnect client from pool and remove it.
        Refer to the disconnect() method of the removed client for details on parameters.
        """
        if client not in self:
            return
        client.disconnect(*args, **kwargs)
        self.remove(client)

    def handle_forever(self):
        """ Main loop of the pool: handle clients forever, until the event loop is stopped. """
        for client in self.clients:
            client.connection.setup_handlers()

        self.eventloop.run()

        for client in self.clients:
            client.connection.remove_handlers()
