## client.py
# Basic IRC client implementation.
import time
import itertools
import logging

from . import async
from . import connection
from . import protocol

__all__ = [ 'AlreadyInChannel', 'NotInChannel', 'BasicClient' ]
PING_DELAY = 30
PING_TIMEOUT = 180
PING_IDENTIFIER = 'pydle-ping-timeout'
DEFAULT_NICKNAME = '<unregistered>'


class IRCError(Exception):
    """ Base class for all pydle errors. """
    pass

class NotInChannel(IRCError):
    def __init__(self, channel):
        super().__init__('Not in channel: {}'.format(channel))
        self.channel = channel

class AlreadyInChannel(IRCError):
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
        self._reset_connection_attributes()
        self._reset_attributes()

        if kwargs:
            self.logger.warning('Unused arguments: %s', ', '.join(kwargs.keys()))

    def _reset_attributes(self):
        """ Reset attributes. """
        # Record-keeping.
        self.channels = {}
        self.users = {}

        # Buffers and locks.
        self._last_data_received = time.time()
        self._receive_buffer = b''
        self._requests = {}
        self._ping_checker_handle = None
        self._ping_timeout_handle = None

        # Misc.
        self.logger = logging.getLogger(__name__)

        # Public connection attributes.
        self.nickname = DEFAULT_NICKNAME
        self.network = None

    def _reset_connection_attributes(self):
        """ Reset connection attributes. """
        self.connection = None
        self.encoding = None
        self._has_quit = False
        self._autojoin_channels = []
        self._reconnect_attempts = 0


    ## Connection.

    def connect(self, hostname=None, port=None, reconnect=False, eventloop=None, **kwargs):
        """ Connect to IRC server. """
        if (not hostname or not port) and not reconnect:
            raise ValueError('Have to specify hostname and port if not reconnecting.')

        # Disconnect from current connection.
        if self.connected:
            self.disconnect()

        # Set event loop.
        if eventloop:
            self.eventloop = eventloop
        elif not self.eventloop:
            self.eventloop = async.EventLoop()

        # Reset attributes and connect.
        if not reconnect:
            self._reset_connection_attributes()
        self._connect(hostname=hostname, port=port, reconnect=reconnect, **kwargs)

        # Schedule pinger.
        self._ping_checker_handle = self.eventloop.schedule_periodically(PING_DELAY, self._check_ping)
        # Set logger name.
        self.logger = logging.getLogger(self.__class__.__name__ + ':' + self.server_tag)

    def disconnect(self):
        """ Disconnect from server. """
        if self.connected:
            # Unschedule remaining ping handlers.
            self.eventloop.unschedule(self._ping_checker_handle)
            if self._ping_timeout_handle:
                self.eventloop.unschedule(self._ping_timeout_handle)

            # Shutdown connection.
            self.connection.off('read', self.on_data)
            self.connection.off('error', self.on_data_error)
            self.connection.disconnect()

            # Callback.
            self.on_disconnect(self._has_quit)

            # Reset any attributes.
            self._reset_attributes()

    def _connect(self, hostname, port, reconnect=False, channels=[], encoding=protocol.DEFAULT_ENCODING, source_address=None):
        """ Connect to IRC host. """
        # Create connection if we can't reuse it.
        if not reconnect or not self.connection:
            self._autojoin_channels = channels
            self.connection = connection.Connection(hostname, port, source_adress=source_address, eventloop=self.eventloop)
            self.encoding = encoding

        # Connect.
        self.connection.connect()
        # Add handlers.
        self.connection.on('read', self.on_data)
        self.connection.on('error', self.on_data_error)

    def _reconnect_delay(self):
        """ Calculate reconnection delay. """
        if self.RECONNECT_ON_ERROR and self.RECONNECT_DELAYED:
            if self._reconnect_attempts > len(self.RECONNECT_DELAYS):
                return self.RECONNECT_DELAYS[-1]
            else:
                return self.RECONNECT_DELAYS[self._reconnect_attempts]
        else:
            return 0

    def _check_ping(self):
        """ Check if we should ping the server. """
        if time.time() - self._last_data_received >= PING_DELAY and not self._ping_timeout_handle:
            # PING_DELAY time of no data. Send a ping.
            self.ping(PING_IDENTIFIER)
            self._ping_timeout_handle = self.eventloop.schedule_in(PING_TIMEOUT, self._on_ping_timeout)

    def _on_pong_received(self, identifier):
        """ Received pong from server. Check if it goes for us. """
        if identifier == PING_IDENTIFIER:
            # Unschedule ping timeout.
            self.eventloop.unschedule(self._ping_timeout_handle)
            self._ping_timeout_handle = None

    def _on_ping_timeout(self):
        """ No pong received from server within PONG_TIMEOUT seconds. """
        if self.connected and self._ping_timeout_handle:
            error = TimeoutError('Ping timeout: no pong received from server after {timeout} seconds.'.format(timeout=PING_TIMEOUT))
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
        self.users[nickname] = {
            'nickname': nickname,
            'username': None,
            'realname': None,
            'hostname': None
        }

    def _sync_user(self, nick, metadata):
        # Servers are NOT users.
        if '.' in nick:
            return

        # Create user in database.
        if not nick in self.users:
            self._create_user(nick)

        self.users[nick].update(metadata)

    def _rename_user(self, user, new):
        if user in self.users:
            self.users[new] = self.users[user]
            self.users[new]['nickname'] = new
            del self.users[user]
        else:
            self._create_user(new)

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

    def _format_hostmask(self, nickname):
        user = self.users.get(nickname, {"username": "*", "hostname": "*"})
        return '{n}!{u}@{h}'.format(n=nickname, u=user['username'] or '*', h=user['hostname'] or '*')


    ## IRC helpers.

    def is_channel(self, chan):
        """ Check if given argument is a channel name or not. """
        return True

    def in_channel(self, channel):
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

    def ping(self, identifier=None):
        """ Ping connection with identifier. """
        raise NotImplementedError()


    ## Overloadable callbacks.

    def on_connect(self):
        """ Callback called when the client has connected successfully. """
        # Reset reconnect attempts.
        self._reconnect_attempts = 0

        # Auto-join channels.
        for channel in self._autojoin_channels:
            self.join(channel)

    def on_disconnect(self, expected):
        self._reset_attributes()

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
                time.sleep(delay)
                self.connect(reconnect=True)
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

        self.connection.send(input)

    def handle_forever(self):
        """ Handle data forever. """
        self.connection.run_forever()


    ## Raw message handlers.

    def on_data(self, data):
        """ Handle received data. """
        self._receive_buffer += data
        self._last_data_received = time.time()

        while self._has_message():
            message = self._parse_message()
            self.on_raw(message)

    def on_data_error(self, exception):
        """ Handle error. """
        self.logger.error('Encountered error on socket. Reconnecting.', exc_info=(type(exception), exception, None))
        self.disconnect()

    def on_raw(self, message):
        """ Handle a single message. """
        self.logger.debug('<< [%s] %s %s', message.source or '', message.command, message.params)
        if not message._valid:
            self.logger.warning('Encountered strictly invalid IRC message from server: %s', message._raw)

        if isinstance(message.command, int):
            cmd = str(message.command).zfill(3)
        else:
            cmd = message.command

        # Invoke dispatcher, if we have one.
        method = 'on_raw_' + cmd.lower()
        try:
            handler = getattr(self, method, self.on_unknown)
            self.eventloop.schedule(handler, message)
        except:
            self.logger.exception('Failed to execute %s handler.', method)

    def on_unknown(self, message):
        """ Unknown command. """
        self.logger.warning('Unknown command: [%s] %s %s', message.source, message.command, message.params)

    def _ignored(self, message):
        """ Ignore message. """
        pass


class ClientPool:
    """ A pool of clients. """

    def __init__(self, clients=None):
        if not clients:
            clients = []

        self.clients = set(clients)
        self.client_cycle = itertools.cycle(self.clients)
        self.connpool = connection.ConnectionPool(client.connection for client in self.clients)

    def add(self, client):
        """ Add client to pool. """
        self.clients.add(client)
        self.client_cycle = itertools.cycle(self.clients)
        self.connpool = connection.ConnectionPool(client.connection for client in self.clients)

    def remove(self, client):
        """ Remove client from pool. """
        self.clients.remove(client)
        self.client_cycle = itertools.cycle(self.clients)
        self.connpool = connection.ConnectionPool(client.connection for client in self.clients)


    ## High-level message stuff.

    def has_message(self):
        return self.connpool.has_message()

    def handle_message(self):
        """
        Handle first available message from any client in the pool.
        Tries to be fair towards clients by cycling the start client tries to take a message from.
        """
        if not self.has_message():
            raise connection.NoMessageAvailable('No message available.')

        for client in self.client_cycle:
            if client._has_message():
                return client.poll_single()

    def poll_forever(self):
        """ Enter infinite handle loop. """
        while True:
            self.poll_single()
            self.handle_message()

    def poll_single(self):
        return self.connpool.wait_for_message()
