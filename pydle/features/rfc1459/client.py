## rfc1459.py
# Basic RFC1459 stuff.
import datetime
import copy

from pydle.async import Future
from pydle.client import BasicClient, NotInChannel, AlreadyInChannel
from . import parsing
from . import protocol


class RFC1459Support(BasicClient):
    """ Basic RFC1459 client. """
    DEFAULT_QUIT_MESSAGE = 'Quitting'

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()
        # Limitations.
        self._away_message_length_limit = None
        self._channel_length_limit = protocol.CHANNEL_LENGTH_LIMIT
        self._channel_limit_groups = copy.deepcopy(protocol.CHANNEL_LIMITS_GROUPS)
        self._channel_limits = copy.deepcopy(protocol.CHANNEL_LIMITS)
        self._command_parameter_limit = protocol.PARAMETER_LIMIT
        self._list_limit_groups = copy.deepcopy(protocol.LIST_LIMITS_GROUPS)
        self._list_limits = copy.deepcopy(protocol.LIST_LIMITS)
        self._mode_limit = None
        self._nickname_length_limit = protocol.NICKNAME_LENGTH_LIMIT
        self._target_limits = {}
        self._topic_length_limit = protocol.TOPIC_LENGTH_LIMIT

        # Modes, prefixes.
        self._mode = {}
        self._channel_modes = set(protocol.CHANNEL_MODES)
        self._channel_modes_behaviour = copy.deepcopy(protocol.CHANNEL_MODES_BEHAVIOUR)
        self._channel_prefixes = set(protocol.CHANNEL_PREFIXES)
        self._nickname_prefixes = protocol.NICKNAME_PREFIXES.copy()
        self._status_message_prefixes = set()
        self._user_modes = set(protocol.USER_MODES)
        self._user_modes_behaviour = copy.deepcopy(protocol.USER_MODES_BEHAVIOUR)

        # Registration.
        self.registered = False
        self._registration_attempts = 0
        self._attempt_nicknames = self._nicknames[:]

        # Info.
        self._requests['whois'] = {}
        self._requests['whowas'] = {}
        self._whois_info = {}
        self._whowas_info = {}

        # Misc.
        self.motd = None
        self._case_mapping = protocol.DEFAULT_CASE_MAPPING

    def _reset_connection_attributes(self):
        super()._reset_connection_attributes()
        self.password = None

    def _create_channel(self, channel):
        super()._create_channel(channel)
        self.channels[channel].update({
            'modes': {},
            'topic': None,
            'topic_by': None,
            'topic_set': None,
            'created': None,
            'password': None,
            'banlist': None,
            'public': True
        })

    def _create_user(self, nickname):
        super()._create_user(nickname)
        self.users[nickname].update({
            'account': None,
            'away': False,
            'away_message': None,
        })

    def _rename_user(self, user, new):
        super()._rename_user(user, new)

        # Rename in mode lists, too.
        for ch in self.channels.values():
            for mode in self._nickname_prefixes.values():
                if mode in ch['modes'] and user in ch['modes'][mode]:
                    ch['modes'][mode].remove(user)
                    ch['modes'][mode].append(new)

    def _destroy_user(self, user, channel):
        if channel:
            channels = [ self.channels[channel] ]
        else:
            channels = self.channels.values()

        # Remove user from status list too.
        for ch in channels:
            for status in self._nickname_prefixes.values():
                if status in ch['modes'] and nickname in ch['modes'][status]:
                    ch['modes'][status].remove(nickname)

    def _parse_user(self, data):
        nickname, username, host = parsing.parse_user(data)

        metadata = {}
        metadata['nickname'] = nickname
        if username:
            metadata['username'] = username
        if host:
            metadata['hostname'] = host
        return nickname, metadata

    def _parse_user_modes(self, user, modes, current=None):
        if current is None:
            current = self.users[user]['modes']
        return parsing.parse_modes(modes, current, behaviour=self._user_modes_behaviour)

    def _parse_channel_modes(self, channel, modes, current=None):
        if current is None:
            current = self.channels[channel]['modes']
        return parsing.parse_modes(modes, current, behaviour=self._channel_modes_behaviour)


    ## Connection.

    def connect(self, hostname=None, port=None, password=None, **kwargs):
        port = port or protocol.DEFAULT_PORT

        # Connect...
        super().connect(hostname, port, **kwargs)
        # Set password.
        self.password = password
        # And initiate the IRC connection.
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

    def _registration_completed(self, message):
        """ We're connected and registered. Receive proper nickname and emit fake NICK message. """
        if not self.registered:
            self.registered = True
            target = message.params[0]
            fakemsg = self._create_message('NICK', target, source=self.nickname)
            self.on_raw_nick(fakemsg)

    ## Message handling.

    def _has_message(self):
        """ Whether or not we have messages available for processing. """
        sep = protocol.MINIMAL_LINE_SEPARATOR.encode(self.encoding)
        return sep in self._receive_buffer

    def _create_message(self, command, *params, **kwargs):
        return parsing.RFC1459Message(command, params, **kwargs)

    def _parse_message(self):
        sep = protocol.MINIMAL_LINE_SEPARATOR.encode(self.encoding)
        message, _, data = self._receive_buffer.partition(sep)
        self._receive_buffer = data
        return parsing.RFC1459Message.parse(message + sep, encoding=self.encoding)

    ## IRC API.

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

    def quit(self, message=None):
        """ Quit network. """
        if message is None:
            message = self.DEFAULT_QUIT_MESSAGE

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
        hostmask = self._format_hostmask(self.nickname)
        # Leeway.
        chunklen = protocol.MESSAGE_LENGTH_LIMIT - len('{hostmask} PRIVMSG {target} :'.format(hostmask=hostmask, target=target)) - 25

        for line in message.replace('\r', '').split('\n'):
            for chunk in chunkify(line, chunklen):
                self.rawmsg('PRIVMSG', target, chunk)

    def notice(self, target, message):
        """ Notice channel or user. """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel('Not in channel {}'.format(target))

        hostmask = self._format_hostmask(self.nickname)
        # Leeway.
        chunklen = protocol.MESSAGE_LENGTH_LIMIT - len('{hostmask} NOTICE {target} :'.format(hostmask=hostmask, target=target)) - 25

        for line in message.replace('\r', '').split('\n'):
            for chunk in chunkify(line, chunklen):
                self.rawmsg('NOTICE', target, chunk)

    def mode(self, target, *modes):
        """ Set mode on target. """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel('Not in channel {}'.format(target))

        self.rawmsg('MODE', target, *modes)

    def topic(self, target, topic):
        """ Set topic on channel. """
        if not self.is_channel(target):
            raise ValueError('Not a channel: {}'.format(target))

        self.rawmsg('TOPIC', target, topic)

    def away(self, message):
        """ Mark self as away. """
        self.rawmsg('AWAY', message)

    def back(self):
        """ Mark self as not away. """
        self.rawmsg('AWAY')

    def whois(self, nickname):
        """
        Return information about user.
        This is an asynchronous method: decorate the calling function with `pydle.coroutine`,
        and yield from this function as follows:
          info = yield self.whois('Nick')
        """

        if " " in nickname:
            fut = Future()
            fut.set_result(None)
            return fut

        if nickname not in self._requests['whois']:
            self.rawmsg('WHOIS', nickname)
            self._whois_info[nickname] = {
                'oper': False,
                'idle': 0,
                'away': False,
                'away_message': None
            }

            # Create a future for when the WHOIS requests succeeds.
            self._requests['whois'][nickname] = Future()

        return self._requests['whois'][nickname]

    def whowas(self, nickname):
        """
        Return information about offline user.
        This is an asynchronous method: decorate the calling function with `pydle.coroutine`,
        and yield from this function as follows:
          info = yield self.whois('Nick')
        """
        if nickname not in _self.requests['whowas']:
            self.rawmsg('WHOWAS', nickname)
            self._whowas_info[nickname] = {}

            # Create a future for when the WHOWAS requests succeeds.
            self._requests['whowas'][nickname] = Future()

        return self._requests['whowas'][nickname]


    ## IRC helpers.

    def normalize(self, s):
        return parsing.normalize(s, case_mapping=self._case_mapping)

    def is_channel(self, chan):
        """ Check if given argument is a channel name or not. """
        return any(chan.startswith(prefix) for prefix in self._channel_prefixes)

    def is_same_nick(self, left, right):
        """ Check if given nicknames are equal in the server's case mapping. """
        return self.normalize(left) == self.normalize(right)

    def is_same_channel(self, left, right):
        """ Check if given nicknames are equal in the server's case mapping. """
        return self.normalize(left) == self.normalize(right)


    ## Overloadable callbacks.

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


    ## Callback handlers.

    def on_raw_invite(self, message):
        """ INVITE command. """
        nick, metadata = self._parse_user(message.source)
        self._sync_user(nick, metadata)

        target, channel = message.params
        target, metadata = self._parse_user(target)

        if self.is_same_nick(self.nickname, target):
            self.on_invite(channel, nick)

    def on_raw_join(self, message):
        """ JOIN command. """
        nick, metadata = self._parse_user(message.source)
        self._sync_user(nick, metadata)

        channels = message.params[0].split(',')
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

    def on_raw_kick(self, message):
        """ KICK command. """
        kicker, kickermeta = self._parse_user(message.source)
        self._sync_user(kicker, kickermeta)

        if len(message.params) > 2:
            channels, targets, reason = message.params
        else:
            channels, targets = message.params
            reason = None

        channels = channels.split(',')
        targets = targets.split(',')

        for channel, target in zip(channels, targets):
            target, targetmeta = self._parse_user(target)
            self._sync_user(target, targetmeta)

            if self.is_same_nick(target, self.nickname):
                self._destroy_channel(channel)
            else:
                # Update nick list on channel.
                if self.in_channel(channel):
                    self._destroy_user(target, channel)

            self.on_kick(channel, target, kicker, reason)

    def on_raw_kill(self, message):
        """ KILL command. """
        by, bymeta = self._parse_user(message.source)
        target, targetmeta = self._parse_user(message.params[0])
        reason = message.params[1]

        self._sync_user(target, targetmeta)
        if by in self.users:
            self._sync_user(by, bymeta)

        self.on_kill(target, by, reason)
        if self.is_same_nick(self.nickname, target):
            self.disconnect()
        else:
            self._destroy_user(target)

    def on_raw_mode(self, message):
        """ MODE command. """
        nick, metadata = self._parse_user(message.source)
        target, modes = message.params[0], message.params[1:]

        self._sync_user(nick, metadata)
        if self.is_channel(target):
            if self.in_channel(target):
                # Parse modes.
                self.channels[target]['modes'] = self._parse_channel_modes(target, modes)

                self.on_mode_change(target, modes, nick)
        else:
            target, targetmeta = self._parse_user(target)
            self._sync_user(target, targetmeta)

            # Update own modes.
            if self.is_same_nick(self.nickname, nick):
                self._mode = self._parse_user_modes(nick, modes, current=self._mode)

            self.on_user_mode_change(modes)

    def on_raw_nick(self, message):
        """ NICK command. """
        nick, metadata = self._parse_user(message.source)
        new = message.params[0]

        self._sync_user(nick, metadata)
        # Acknowledgement of nickname change: set it internally, too.
        # Alternatively, we were force nick-changed. Nothing much we can do about it.
        if self.is_same_nick(self.nickname, nick):
            self._nickname = new

        # Go through all user lists and replace.
        self._rename_user(nick, new)

        # Call handler.
        self.on_nick_change(nick, new)

    def on_raw_notice(self, message):
        """ NOTICE command. """
        nick, metadata = self._parse_user(message.source)
        target, message = message.params

        self._sync_user(nick, metadata)

        self.on_notice(target, nick, message)
        if self.is_channel(target):
            self.on_channel_notice(target, nick, message)
        else:
            self.on_private_notice(nick, message)

    def on_raw_part(self, message):
        """ PART command. """
        nick, metadata = self._parse_user(message.source)
        channels = message.params[0].split(',')
        if len(message.params) > 1:
            reason = message.params[1]
        else:
            reason = None

        self._sync_user(nick, metadata)
        if self.is_same_nick(self.nickname, nick):
            # We left the channel. Remove from channel list. :(
            for channel in channels:
                if self.in_channel(channel):
                    self._destroy_channel(channel)
                    self.on_part(channel, nick, reason)
        else:
            # Someone else left. Remove them.
            for channel in channels:
                self._destroy_user(nick, channel)
                self.on_part(channel, nick, reason)

    def on_raw_ping(self, message):
        """ PING command. """
        # Respond with a pong.
        self.rawmsg('PONG', *message.params)

    def on_raw_privmsg(self, message):
        """ PRIVMSG command. """
        nick, metadata = self._parse_user(message.source)
        target, message = message.params

        self._sync_user(nick, metadata)

        self.on_message(target, nick, message)
        if self.is_channel(target):
            self.on_channel_message(target, nick, message)
        else:
            self.on_private_message(nick, message)

    def on_raw_quit(self, message):
        """ QUIT command. """
        nick, metadata = self._parse_user(message.source)

        self._sync_user(nick, metadata)
        if message.params:
            reason = message.params[0]
        else:
            reason = None

        self.on_quit(nick, reason)
        # Remove user from database.
        if not self.is_same_nick(self.nickname, nick):
            self._destroy_user(nick)
        # Else, we quit.
        elif self.connected:
            self.disconnect()

    def on_raw_topic(self, message):
        """ TOPIC command. """
        setter, settermeta = self._parse_user(message.source)
        target, topic = message.params

        self._sync_user(setter, settermeta)

        # Update topic in our own channel list.
        if self.in_channel(target):
            self.channels[target]['topic'] = topic
            self.channels[target]['topic_by'] = setter
            self.channels[target]['topic_set'] = datetime.datetime.now()

        self.on_topic_change(target, topic, setter)


    ## Numeric responses.

    # Since RFC1459 specifies no specific banner message upon completion of registration,
    # take any of the below commands as an indication that registration succeeded.

    on_raw_001 = _registration_completed # Welcome message.
    on_raw_002 = _registration_completed # Server host.
    on_raw_003 = _registration_completed # Server creation time.

    def on_raw_004(self, message):
        """ Basic server information. """
        hostname, ircd, user_modes, channel_modes = message.params[:4]

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

    def on_raw_301(self, message):
        """ User is away. """
        nickname, message = message.params[0]
        info = {
            'away': True,
            'away_message': message
        }

        if nickname in self.users:
            self._sync_user(nickname, info)
        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_307(self, message):
        """ User is identified (Anope). """
        target, nickname = message.params[:2]
        info = {
            'identified': True
        }

        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_311(self, message):
        """ WHOIS user info. """
        target, nickname, username, hostname, _, realname = message.params
        info = {
            'username': username,
            'hostname': hostname,
            'realname': realname
        }

        self._sync_user(nickname, info)
        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_312(self, message):
        """ WHOIS server info. """
        target, nickname, server, serverinfo = message.params
        info = {
            'server': server,
            'server_info': serverinfo
        }

        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)
        if nickname in self._requests['whowas']:
            self._whowas_info[nickname].update(info)

    def on_raw_313(self, message):
        """ WHOIS operator info. """
        target, nickname = message.params[:2]
        info = {
            'oper': True
        }

        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_314(self, message):
        """ WHOWAS user info. """
        target, nickname, username, hostname, _, realname = message.params
        info = {
            'username': username,
            'hostname': hostname,
            'realname': realname
        }

        if nickname in self._requests['whowas']:
            self._whowas_info[nickname].update(info)

    on_raw_315 = BasicClient._ignored    # End of /WHO list.

    def on_raw_317(self, message):
        """ WHOIS idle time. """
        target, nickname, idle_time = message.params[:3]
        info = {
            'idle': int(idle_time),
        }

        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_318(self, message):
        """ End of /WHOIS list. """
        target, nickname =  message.params[:2]

        # Mark future as done.
        if nickname in self._requests['whois']:
            future = self._requests['whois'].pop(nickname)
            future.set_result(self._whois_info[nickname])

    def on_raw_319(self, message):
        """ WHOIS active channels. """
        target, nickname, channels = message.params[:3]
        channels = { channel.lstrip() for channel in channels.strip().split(' ') }
        info = {
            'channels': channels
        }

        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_324(self, message):
        """ Channel mode. """
        target, channel = message.params[:2]
        modes = message.params[2:]
        if not self.in_channel(channel):
            return

        self.channels[channel]['modes'] = self._parse_channel_modes(channel, modes)

    def on_raw_329(self, message):
        """ Channel creation time. """
        target, channel, timestamp = message.params
        if not self.in_channel(channel):
            return

        self.channels[channel]['created'] = datetime.datetime.fromtimestamp(int(timestamp))

    def on_raw_330(self, message):
        """ WHOIS account name (Atheme). """
        target, nickname, account = message.params[:3]
        info = {
            'account': account
        }

        if nickname in self.users:
            self._sync_user(nickname, info)
        if nickname in self._requests['whois']:
            self._whois_info[nickname].update(info)

    def on_raw_332(self, message):
        """ Current topic on channel join. """
        target, channel, topic = message.params
        if not self.in_channel(channel):
            return

        self.channels[channel]['topic'] = topic

    def on_raw_333(self, message):
        """ Topic setter and time on channel join. """
        target, channel, setter, timestamp = message.params
        if not self.in_channel(channel):
            return

        # No need to sync user since this is most likely outdated info.
        self.channels[channel]['topic_by'] = self._parse_user(setter)[0]
        self.channels[channel]['topic_set'] = datetime.datetime.fromtimestamp(int(timestamp))

    def on_raw_353(self, message):
        """ Response to /NAMES. """
        target, visibility, channel, names = message.params
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
            # Make entry safe for _parse_user().
            safe_entry = entry.lstrip(''.join(self._nickname_prefixes.keys()))
            # Parse entry and update database.
            nick, metadata = self._parse_user(safe_entry)
            self._sync_user(nick, metadata)

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

    on_raw_366 = BasicClient._ignored # End of /NAMES list.

    def on_raw_375(self, message):
        """ Start message of the day. """
        self._registration_completed(message)
        self.motd = message.params[1] + '\n'

    def on_raw_372(self, message):
        """ Append message of the day. """
        self.motd += message.params[1] + '\n'

    def on_raw_376(self, message):
        """ End of message of the day. """
        self.motd += message.params[1] + '\n'

        # MOTD is done, let's tell our bot the connection is ready.
        self.on_connect()

    def on_raw_401(self, message):
        """ No such nick/channel. """
        nickname = message.params[1]
        if nickname in self._requests['whois']:
            future = self._requests['whois'].pop(nickname)
            future.set_result(None)
            del self._whois_info[nickname]

    def on_raw_402(self, message):
        """ No such server. """
        return self.on_raw_401(message)

    def on_raw_422(self, message):
        """ MOTD is missing. """
        self.motd = None
        self.on_connect()

    def on_raw_421(self, message):
        """ Server responded with 'unknown command'. """
        self.logger.warning('Server responded with "Unknown command: %s"'.format(message.params[0]))

    def on_raw_432(self, message):
        """ Erroneous nickname. """
        if not self.registered:
            # Nothing else we can do than try our next nickname.
            self.on_raw_433(message)

    def on_raw_433(self, message):
        """ Nickname in use. """
        if not self.registered:
            self._registration_attempts += 1
            # Attempt to set new nickname.
            if self._attempt_nicknames:
                self.nickname = self._attempt_nicknames.pop(0)
            else:
                self.nickname = self._nicknames[0] + '_' * (self._registration_attempts - len(self._nicknames))

    on_raw_436 = BasicClient._ignored # Nickname collision, issued right before the server kills us.

    def on_raw_451(self, message):
        """ We have to register first before doing X. """
        # TODO: Implement. Warning?
        pass

    on_raw_451 = BasicClient._ignored # You have to register first.
    on_raw_462 = BasicClient._ignored # You may not re-register.


## Helpers.

def chunkify(message, chunksize):
    while message:
        chunk = message[:chunksize]
        message = message[chunksize:]
        yield chunk
