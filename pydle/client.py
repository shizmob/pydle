## client.py
# Basic IRC client implementation.
import os
import datetime
import time
import itertools

from . import connection
from . import protocol
from . import log

__all__ = [ 'AlreadyInChannel', 'NotInChannel', 'BasicClient' ]


class IRCError(Exception):
    """ Base class for all pydle errors. """
    pass

class NotInChannel(IRCError):
    pass

class AlreadyInChannel(IRCError):
    pass


class BasicClient:
    """ Basic RFC1459 IRC client. """
    DEFAULT_QUIT_MESSAGE = 'Quitting'

    RECONNECT = True
    RECONNECT_MAX_ATTEMPTS = 3
    RECONNECT_DELAYED = True
    RECONNECT_DELAYS = [0, 30, 120, 600]

    def __init__(self, nickname, fallback_nicknames=[], username=None, realname=None, **kwargs):
        """ Create a client. """
        self._nicknames = [nickname] + fallback_nicknames
        self.username = username or nickname.lower()
        self.realname = realname or nickname
        self.logger = log.Logger()
        self._reset_connection_attributes()
        self._reset_attributes()

        if kwargs:
            self.logger.warn('Unused arguments: {kw}', kw=kwargs)

    def _reset_attributes(self):
        """ Reset attributes. """
        ## Internal variables.

        # Connection and basic state.
        self._registration_attempts = 0
        self._attempt_nicknames = self._nicknames[:]
        self._mode = {}

        # Record-keeping.
        self.channels = {}
        self.users = {}

        # Capabilities and features.
        self._extban_types = []

        # Limits.
        self._away_message_length_limit = None
        self._channel_length_limit = protocol.CHANNEL_LENGTH_LIMIT
        self._channel_limit_groups = protocol.CHANNEL_LIMITS_GROUPS.copy()
        self._channel_limits = protocol.CHANNEL_LIMITS.copy()
        self._command_parameter_limit = protocol.PARAMETER_LIMIT
        self._list_limit_groups = {}
        self._list_limits = {}
        self._mode_limit = None
        self._nickname_length_limit = protocol.NICKNAME_LENGTH_LIMIT
        self._target_limits = {}
        self._topic_length_limit = protocol.TOPIC_LENGTH_LIMIT

        # Modes and prefixes.
        self._channel_modes = set(protocol.CHANNEL_MODES)
        self._channel_modes_behaviour = protocol.CHANNEL_MODES_BEHAVIOUR.copy()
        self._channel_prefixes = set(protocol.CHANNEL_PREFIXES)
        self._extban_prefix = None
        self._nickname_prefixes = protocol.NICKNAME_PREFIXES.copy()
        self._status_message_prefixes = set()
        self._user_modes = set(protocol.USER_MODES)

        # Misc.
        self._case_mapping = protocol.CASE_MAPPING
        self.logger.name = self.__class__.__name__

        ## Public connection attributes.
        self.nickname = '<unregistered>'
        self.registered = False
        self.motd = None
        self.network = None

    def _reset_connection_attributes(self):
        """ Reset connection attributes. """
        self.connection = None
        self.password = None
        self._autojoin_channels = []
        self._has_quit = False
        self._reconnect_attempts = 0


    ## Connection.

    def connect(self, hostname, port=None, password=None, channels=[], encoding='utf-8'):
        """ Connect to IRC server. """
        # Disconnect from current connection.
        if self.connected:
            self.disconnect()
            self._reset_connection_attributes()

        self.password = password
        self._autojoin_channels = channels

        # Create connection.
        self.connection = connection.Connection(hostname, port or protocol.DEFAULT_PORT, encoding=encoding)
        # Connect.
        self.connection.connect()

        # And initiate the IRC connection.
        self._register()

    def disconnect(self):
        """ Disconnect from server. """
        if self.connected:
            self.connection.disconnect()
            self.on_disconnect()

            # Reset any attributes.
            self._reset_attributes()

    def reconnect(self):
        """ Reconnect to server. """
        if self.connected:
            self.disconnect()

        # Reuse connection.
        self.connection.connect()

        # Set logger name.
        self.logger.name = self.__class__.__name__ + ':' + self.server_tag

        # Initiate registration.
        self._register()

    def _register(self):
        """ Perform IRC connection registration. """
        if self.registered:
            return

        self._registration_attempts += 1

        # Password first.
        if self.password:
            self.rawmsg('PASS', self.password)

        # Then nickname...
        self.nickname = self._attempt_nicknames.pop(0)

        # And now for the rest of the user information.
        self.rawmsg('USER', self.username, '0', '*', self.realname)

    def _registration_completed(self, source, params):
        """ We're connected and registered. Receive proper nickname and emit fake NICK message. """
        self.registered = True

        target = params[0]
        self.on_raw_nick(self.nickname, [ target ])

    def _reconnect_delay(self):
        """ Calculate reconnection delay. """
        if self.RECONNECT and self.RECONNECT_DELAYED:
            if self._reconnect_attempts > len(self.RECONNECT_DELAYS):
                return self.RECONNECT_DELAYS[-1]
            else:
                return self.RECONNECT_DELAYS[self._reconnect_attempts]
        else:
            return 0


    ## Internal database management.

    def _create_channel(self, channel):
        self.channels[channel] = {
            'topic': None,
            'topic_by': None,
            'topic_set': None,
            'users': set(),
            'modes': {},
            'created': None,
            'password': None,
            'banlist': None,
            'public': True
        }

    def _destroy_channel(self, channel):
        del self.channels[channel]


    def _create_user(self, nickname):
        self.users[nickname] = {
            'away': False,
            'away_message': None,
            'username': None,
            'realname': None,
            'hostname': None
        }

    def _sync_user(self, nick, user, host):
        # Servers are NOT users.
        if '.' in nick:
            return

        # Create user in database.
        if not nick in self.users:
            self._create_user(nick)

        # Update user/host combination.
        if user:
            self.users[nick]['username'] = user
        if host:
            self.users[nick]['hostname'] = host

    def _rename_user(self, user, new):
        if user in self.users:
            self.users[new] = self.users[user]
            del self.users[user]
        else:
            self._create_user(new)

        for ch in self.channels.values():
            # Rename user in channel list.
            if user in ch['users']:
                ch['users'].discard(user)
                ch['users'].add(new)

            # Also replace in channel status lists.
            for mode in self._nickname_prefixes.values():
                if mode in ch['modes'] and user in ch['modes'][mode]:
                    ch['modes'][mode].remove(user)
                    ch['modes'][mode].append(new)

    def _destroy_user(self, nickname, channel=None):
        if channel:
            channels = [ self.channels[channel] ]
        else:
            channels = self.channels.values()

        for ch in channels:
            # Remove from nicklist.
            ch['users'].discard(nickname)

            # Remove from statuses.
            for status in self._nickname_prefixes.values():
                if status in ch['modes'] and nickname in ch['modes'][status]:
                    ch['modes'][status].remove(nickname)

        # If we're not in any common channels with the user anymore, we have no reliable way to keep their info up-to-date.
        # Remove the user.
        if not channel or not any(nickname in ch['users'] for ch in self.channels.values()):
            del self.users[nickname]


    ## IRC attributes.

    @property
    def connected(self):
        """ Whether or not we are connected. """
        return self.connection and self.connection.connected

    @property
    def nickname(self):
        """ Our currently active nickname. """
        return self._nickname

    @nickname.setter
    def nickname(self, value):
        """ Change nickname. """
        if self.connected:
            self.rawmsg('NICK', value)
        else:
            self._nickname = value

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
        if not message.endswith(protocol.LINE_SEPARATOR):
            message += protocol.LINE_SEPARATOR
        self._send_raw(message)

    def rawmsg(self, command, *params, source=None):
        """ Send raw message. """
        self._send_message(command, *params, source=source)

    def join(self, channel, password=None):
        """ Join channel, optionally with password. """
        if self.in_channel(channel):
            raise AlreadyInChannel('Already in channel {}'.format(channel))

        if password:
            self.rawmsg('JOIN', channel, password)
        else:
            self.rawmsg('JOIN', channel)

    def part(self, channel, message=None):
        """ Leave channel, optionally with message. """
        if not self.in_channel(channel):
            raise NotInChannel('Not in channel {}'.format(channel))

        # Message seems to be an extension to the spec.
        if message:
            self.rawmsg('PART', channel, message)
        else:
            self.rawmsg('PART', channel)

    def quit(self, message=DEFAULT_QUIT_MESSAGE):
        """ Quit network. """
        self._has_quit = True
        self.rawmsg('QUIT', message)
        self.disconnect()

    def cycle(self, channel):
        """ Rejoin channel. """
        if not self.in_channel(channel):
            raise NotInChannel('Not in channel {}'.format(channel))

        password = self.channels[channel]['password']
        self.part(channel)
        self.join(channel, password)

    def message(self, target, message):
        """ Message channel or user. """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel('Not in channel {}'.format(target))

        self.rawmsg('PRIVMSG', target, message)

    def notice(self, target, message):
        """ Notice channel or user. """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel('Not in channel {}'.format(target))

        self.rawmsg('NOTICE', target, message)

    def mode(self, target, *modes):
        """ Set mode on target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel('Not in channel {}'.format(target))

        self.rawmsg('MODE', target, *modes)

    def away(self, message):
        """ Mark self as away. """
        self.rawmsg('AWAY', message)

    def back(self):
        """ Mark self as not away. """
        self.rawmsg('AWAY')


    ## IRC helpers.

    def is_channel(self, chan):
        """ Check if given argument is a channel name or not. """
        return any(chan.startswith(prefix) for prefix in self._channel_prefixes)

    def in_channel(self, channel):
        return channel in self.channels.keys()

    def is_same_nick(self, left, right):
        """ Check if given nicknames are equal in the server's case mapping. """
        return protocol.equals(left, right, case_mapping=self._case_mapping)


    ## Overloadable callbacks.

    def on_connect(self):
        """ Callback called when the client has connected successfully. """
        # Reset reconnect attempts.
        self._reconnect_attempts = 0

        # Auto-join channels.
        for channel in self._autojoin_channels:
            self.join(channel)

    def on_disconnect(self):
        pass

    def on_invite(self, channel, by):
        pass

    def on_join(self, channel, user):
        pass

    def on_kill(self, target, by, reason):
        pass

    def on_kick(self, channel, target, by, reason=None):
        pass

    def on_mode_change(self, channel, modes, by):
        pass

    def on_user_mode_change(self, modes):
        pass

    def on_message(self, target, by, message):
        pass

    def on_channel_message(self, target, by, message):
        pass

    def on_private_message(self, by, message):
        pass

    def on_nick_change(self, old, new):
        pass

    def on_notice(self, target, by, message):
        pass

    def on_channel_notice(self, target, by, message):
        pass

    def on_private_notice(self, by, message):
        pass

    def on_part(self, channel, user, message=None):
        pass

    def on_topic_change(self, channel, message, by):
        pass

    def on_quit(self, user, message=None):
        pass


    ## Message dispatch.

    def _has_message(self, types=None):
        """ Whether or not we have messages available for processing. """
        return self.connection.has_message(types=types)

    def _wait_for_message(self, types=None):
        """ Wait for a received message. """
        self.connection.wait_for_message(types=types)

    def _get_message(self, types=None):
        """ Get a single message. """
        return self.connection.get_message(types=types)

    def _handle_message(self, types=None):
        """ Handle a single message. """
        source, command, params = self._get_message(types=types)
        self.logger.debug('<< [{source}] {command} {args}', source=source or '', command=command, args=params)

        if isinstance(command, int):
            cmd = str(command).zfill(3)
        else:
            cmd = command

        # Invoke dispatcher, if we have one.
        method = 'on_raw_' + cmd.lower()
        if hasattr(self, method):
            getattr(self, method)(source, params)
        # Invoke default method.
        else:
            self.on_unknown(command, source, params)

        return source, command, params

    def _send_raw(self, message):
        """ Send a raw message. """
        self.logger.debug('>>> {msg}', msg=message)
        self.connection.send_string(message)

    def _send_message(self, command, *params, source=None):
        """ Send a message. """
        self.logger.debug('>> [{source}] {command} {args}', source=source or '', command=command, args=params)
        self.connection.send_message(command, *params, source=source)

    def handle_forever(self):
        """ Handle messages forever. Main loop. """
        while True:
            while self.connected:
                try:
                    self._wait_for_message()
                    self._handle_message()
                except connection.NotConnected:
                    break

            if self._has_quit:
                # Nothing to worry about.
                break

            # Unexpected disconnect. Reconnect?
            if self.RECONNECT and (self.RECONNECT_MAX_ATTEMPTS is None or self._reconnect_attempts < self.RECONNECT_MAX_ATTEMPTS):
                # Calculate reconnect delay.
                delay = self._reconnect_delay()
                self._reconnect_attempts += 1

                if delay > 0:
                    self.logger.err('Unexpected disconnect. Attempting to reconnect within {n} seconds.', n=delay)
                else:
                    self.logger.err('Unexpected disconnect. Attempting to reconnect.')

                # Wait and reconnect.
                time.sleep(delay)
                self.reconnect()
            else:
                self.logger.err('Unexpected disconnect. Giving up.')


    ## Raw message handlers.

    def on_unknown(self, command, source, params):
        """ Unknown command. """
        self.logger.warn('Unknown command: [{source}] {command} {params}', source=source, command=command, params=params)

    def _ignored(self, source, params):
        """ Ignore message. """
        pass


    def on_raw_invite(self, source, params):
        """ INVITE command. """
        nick, user, host = protocol.parse_user(source)
        if nick in self.users:
            self._sync_user(nick, user, host)

        target, channel = params
        target = protocol.parse_user(target)

        if self.is_same_nick(self.nickname, nick):
            self.on_invite(channel, user)

    def on_raw_join(self, source, params):
        """ JOIN command. """
        nick, user, host = protocol.parse_user(source)
        self._sync_user(nick, user, host)

        channels = params[0].split(',')
        if self.is_same_nick(self.nickname, nick):
            # Add to our channel list, we joined here.
            for channel in channels:
                if not self.in_channel(channel):
                    self._create_channel(channel)

                # Request channel mode from IRCd.
                self.rawmsg('MODE', channel)
        else:
            # Add user to channel user list.
            for channel in channels:
                if self.in_channel(channel):
                    self.channels[channel]['users'].add(nick)

        for channel in channels:
            self.on_join(channel, nick)

    def on_raw_kick(self, source, params):
        """ KICK command. """
        kicker, kickeruser, kickerhost = protocol.parse_user(source)
        self._sync_user(kicker, kickeruser, kickerhost)

        if len(params) > 2:
            channels, targets, reason = params
        else:
            channels, targets = params
            reason = None

        channels = channels.split(',')
        targets = targets.split(',')

        for channel, target in zip(channels, targets):
            target, targetuser, targethost = protocol.parse_user(target)
            self._sync_user(target, targetuser, targethost)

            # Update nick list on channel.
            if self.in_channel(channel):
                self._destroy_user(target, channel)

            self.on_kick(channel, target, kicker, reason)

    def on_raw_kill(self, source, params):
        """ KILL command. """
        by, byuser, byhost = protocol.parse_user(source)
        target = protocol.parse_user(params[0])[0]
        message = params[1]

        if by in self.users:
            self._sync_user(by, byuser, byhost)

        if self.is_same_nick(self.nickname, target):
            self.disconnect()
        else:
            self._destroy_user(target)

        self.on_kill(target, by, reason)

    def on_raw_mode(self, source, params):
        """ MODE command. """
        nick, user, host = protocol.parse_user(source)
        target, modes = params[0], params[1:]

        self._sync_user(nick, user, host)

        if self.is_channel(target):
            if self.in_channel(target):
                # Parse modes.
                self.channels[target]['modes'] = protocol.parse_channel_modes(modes, self.channels[target]['modes'], behaviour=self._channel_modes_behaviour)

                self.on_mode_change(target, modes, nick)
        else:
            target, targetuser, targethost = protocol.parse_user(target)
            self._sync_user(target, targetuser, targethost)

            # Update own modes.
            if self.is_same_nick(self.nickname, nick):
                self._mode = protocol.parse_user_modes(modes, self._mode)

            self.on_user_mode_change(modes)

    def on_raw_nick(self, source, params):
        """ NICK command. """
        nick, user, host = protocol.parse_user(source)
        new = params[0]

        self._sync_user(nick, user, host)
        # Acknowledgement of nickname change: set it internally, too.
        # Alternatively, we were force nick-changed. Nothing much we can do about it.
        if self.is_same_nick(self.nickname, nick):
            self._nickname = new
            # Reflect logger change.
            self.logger.name = self.__class__.__name__ + ':' + self.server_tag + ':' + self._nickname

        # Go through all user lists and replace.
        self._rename_user(nick, new)

        self.on_nick_change(nick, new)

    def on_raw_notice(self, source, params):
        """ NOTICE command. """
        nick, user, host = protocol.parse_user(source)
        target, message = params

        if nick in self.users:
            self._sync_user(nick, user, host)

        self.on_notice(target, nick, message)
        if self.is_channel(target):
            self.on_channel_notice(target, nick, message)
        else:
            self.on_private_notice(nick, message)

    def on_raw_part(self, source, params):
        """ PART command. """
        nick, user, host = protocol.parse_user(source)
        channels = params[0].split(',')
        if len(params) > 1:
            message = params[1]
        else:
            message = None

        self._sync_user(nick, user, host)

        if self.is_same_nick(self.nickname, nick):
            # We left the channel. Remove from channel list. :(
            for channel in channels:
                if self.in_channel(channel):
                    del self.channels[channel]
        else:
            # Someone else left. Remove them.
            for ch in channels:
                self._destroy_user(nick, ch)

        for channel in channels:
            self.on_part(channel, nick, message)

    def on_raw_ping(self, source, params):
        """ PING command. """
        # Respond with a pong.
        self.rawmsg('PONG', *params)

    def on_raw_privmsg(self, source, params):
        """ PRIVMSG command. """
        nick, user, host = protocol.parse_user(source)
        target, message = params

        if nick in self.users:
            self._sync_user(nick, user, host)

        self.on_message(target, nick, message)
        if self.is_channel(target):
            self.on_channel_message(target, nick, message)
        else:
            self.on_private_message(nick, message)

    def on_raw_quit(self, source, params):
        """ QUIT command. """
        # No need to sync if the user is quitting anyway.
        user = protocol.parse_user(source)[0]
        if params:
            message = params[0]
        else:
            message = None

        # Remove user from database.
        if not self.is_same_nick(self.nickname, user):
            self._destroy_user(user)
        # Else, we quit.
        elif self.connected:
            self.disconnect()

        self.on_quit(user, message)

    def on_raw_topic(self, source, params):
        """ TOPIC command. """
        setter, setteruser, setterhost = protocol.parse_user(source)
        target, message = params

        self._sync_user(setter, setteruser, setterhost)

        # Update topic in our own channel list.
        if self.in_channel(target):
            self.channels[target]['topic'] = message
            self.channels[target]['topic_by'] = setter
            self.channels[target]['topic_set'] = datetime.datetime.now()

        self.on_topic_change(target, message, setter)


    ## Numeric responses.

    # Since RFC1459 specifies no specific banner message upon completion of registration,
    # take any of the below commands as an indication that registration succeeded.

    on_raw_001 = _registration_completed # Welcome message.
    on_raw_002 = _registration_completed # Server host.
    on_raw_003 = _registration_completed # Server creation time.

    def on_raw_004(self, source, params):
        """ Basic server information. """
        hostname, ircd, user_modes, channel_modes = params[:4]

        # Set valid channel and user modes.
        self._channel_modes = set(channel_modes)
        self._user_modes = set(user_modes)

    on_raw_008 = _registration_completed # Server notice mask.
    on_raw_042 = _registration_completed # Unique client ID.
    on_raw_250 = _registration_completed # Connection statistics.
    on_raw_251 = _registration_completed # Amount of users online.
    on_raw_252 = _registration_completed # Amount of operators online.
    on_raw_253 = _registration_completed # Amount of unknown connections.
    on_raw_254 = _registration_completed # Amount of channels.
    on_raw_255 = _registration_completed # Amount of local users and servers.
    on_raw_265 = _registration_completed # Amount of local users.
    on_raw_266 = _registration_completed # Amount of global users.

    def on_raw_324(self, source, params):
        """ Channel mode. """
        target, channel, modes = params[0], params[1], params[2:]
        if not self.in_channel(channel):
            return

        self.channels[channel]['modes'] = protocol.parse_channel_modes(modes, self.channels[channel]['modes'], behaviour=self._channel_modes_behaviour)

    def on_raw_329(self, source, params):
        """ Channel creation time. """
        target, channel, timestamp = params
        if not self.in_channel(channel):
            return

        self.channels[channel]['created'] = datetime.datetime.fromtimestamp(int(timestamp))

    def on_raw_332(self, source, params):
        """ Current topic on channel join. """
        target, channel, topic = params
        if not self.in_channel(channel):
            return

        self.channels[channel]['topic'] = topic

    def on_raw_333(self, source, params):
        """ Topic setter and time on channel join. """
        target, channel, setter, timestamp = params
        if not self.in_channel(channel):
            return

        # No need to sync user since this is most likely outdated info.
        self.channels[channel]['topic_by'] = protocol.parse_user(setter)[0]
        self.channels[channel]['topic_set'] = datetime.datetime.fromtimestamp(int(timestamp))

    def on_raw_353(self, source, params):
        """ Response to /NAMES. """
        target, visibility, channel, names = params
        if not self.in_channel(channel):
            return

        # Set channel visibility.
        if visibility == protocol.PUBLIC_CHANNEL_SIGIL:
            self.channels[channel]['public'] = True
        elif visibility in (protocol.PRIVATE_CHANNEL_SIGIL, protocol.SECRET_CHANNEL_SIGIL):
            self.channels[channel]['public'] = False

        # Update channel user list.
        for entry in names.split():
            statuses = []
            # Make entry safe for protocol.parse_user().
            safe_entry = entry.lstrip(''.join(self._nickname_prefixes.keys()))
            # Parse entry and update database.
            nick, user, host = protocol.parse_user(safe_entry)
            self._sync_user(nick, user, host)

            # Get prefixes.
            prefixes = set(entry.replace(safe_entry, ''))

            # Check, record and strip status prefixes.
            for prefix, status in self._nickname_prefixes.items():
                # Add to list of statuses by user.
                if prefix in prefixes:
                    statuses.append(status)

            # Add user to user list.
            self.channels[channel]['users'].add(nick)
            # And to channel modes..
            for status in statuses:
                if status not in self.channels[channel]['modes']:
                    self.channels[channel]['modes'][status] = []
                self.channels[channel]['modes'][status].append(nick)

    on_raw_366 = _ignored # End of /NAMES list.

    def on_raw_375(self, source, params):
        """ Start message of the day. """
        self._registration_completed(source, params)
        self.motd = params[1] + '\n'

    def on_raw_372(self, source, params):
        """ Append message of the day. """
        self.motd += params[1] + '\n'

    def on_raw_376(self, source, params):
        """ End of message of the day. """
        self.motd += params[1] + '\n'

        # MOTD is done, let's tell our bot the connection is ready.
        self.on_connect()

    def on_raw_421(self, source, params):
        """ Server responded with 'unknown command'. """
        self.logger.warn('Server responded with "Unknown command: {}"'.format(params[0]))

    def on_raw_433(self, source, params):
        """ Nickname in use. """
        if not self.registered:
            self._registration_attempts += 1
            # Attempt to set new nickname.
            if not self._attempt_nicknames:
                self.nickname = self._nicknames[0] + '_' * (self._registration_attempts - len(self._nicknames))
            else:
                self.nicknames = self._attempt_nicknames.pop(0)

    def on_raw_432(self, source, params):
        """ Erroneous nickname. """
        if not self.registered:
            self.on_raw_432(source, params)

    on_raw_436 = _ignored # Nickname collision, issued right before the server kills us.

    def on_raw_451(self, source, params):
        """ We have to register first before doing X. """
        # TODO: Implement. Warning?
        pass

    on_raw_451 = _ignored # You have to register first.
    on_raw_462 = _ignored # You may not re-register.


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
                return client._handle_message()

    def handle_forever(self):
        """ Enter infinite handle loop. """
        while True:
            self.wait_for_message()
            self.handle_message()

    def wait_for_message(self):
        return self.connpool.wait_for_message()

