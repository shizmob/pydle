## rfc1459.py
# Basic RFC1459 stuff.
import copy
import datetime
import ipaddress
import itertools

from pydle.client import BasicClient, NotInChannel, AlreadyInChannel
from . import parsing, protocol


class RFC1459Support(BasicClient):
    """ Basic RFC1459 client. """
    DEFAULT_QUIT_MESSAGE = 'Quitting'

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()
        # Casemapping.
        self._case_mapping = protocol.DEFAULT_CASE_MAPPING

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
        self._pending['whois'] = parsing.NormalizingDict(case_mapping=self._case_mapping)
        self._pending['whowas'] = parsing.NormalizingDict(case_mapping=self._case_mapping)
        self._whois_info = parsing.NormalizingDict(case_mapping=self._case_mapping)
        self._whowas_info = parsing.NormalizingDict(case_mapping=self._case_mapping)

        # Misc.
        self.motd = None
        self.channels = parsing.NormalizingDict(self.channels, case_mapping=self._case_mapping)
        self.users = parsing.NormalizingDict(self.users, case_mapping=self._case_mapping)

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
        if nickname in self.users:
            self.users[nickname].update({
                'away': False,
                'away_message': None,
            })

    def _rename_user(self, user, new):
        super()._rename_user(user, new)

        # Rename in mode lists, too.
        for ch in self.channels.values():
            for status in self._nickname_prefixes.values():
                if status in ch['modes'] and user in ch['modes'][status]:
                    ch['modes'][status].remove(user)
                    ch['modes'][status].append(new)

    def _destroy_user(self, user, channel=None):
        if channel:
            channels = [self.channels[channel]]
        else:
            channels = self.channels.values()

        # Remove user from status list too.
        for ch in channels:
            for status in self._nickname_prefixes.values():
                if status in ch['modes'] and user in ch['modes'][status]:
                    ch['modes'][status].remove(user)

    def _parse_user(self, data):
        if data:
            nickname, username, host = parsing.parse_user(data)

            metadata = {}
            metadata['nickname'] = nickname
            if username:
                metadata['username'] = username
            if host:
                metadata['hostname'] = host
        else:
            return None, {}
        return nickname, metadata

    def _parse_user_modes(self, user, modes, current=None):
        if current is None:
            current = self.users[user]['modes']
        return parsing.parse_modes(modes, current, behaviour=self._user_modes_behaviour)

    def _parse_channel_modes(self, channel, modes, current=None):
        if current is None:
            current = self.channels[channel]['modes']
        return parsing.parse_modes(modes, current, behaviour=self._channel_modes_behaviour)

    def _format_host_range(self, host, range, allow_everything=False):
        # IPv4?
        try:
            addr = ipaddress.IPv4Network(host, strict=False)
            max = 4 if allow_everything else 3

            # Round up subnet to nearest octet.
            subnet = addr.prefixlen + (8 - addr.prefixlen % 8)
            # Remove range mask.
            subnet -= min(range, max) * 8

            rangeaddr = addr.supernet(new_prefix=subnet).exploded.split('/', 1)[0]
            return rangeaddr.replace('0', '*')
        except ValueError:
            pass

        # IPv6?
        try:
            addr = ipaddress.IPv6Network(host, strict=False)
            max = 4 if allow_everything else 3

            # Round up subnet to nearest 32-et.
            subnet = addr.prefixlen + (32 - addr.prefixlen % 32)
            # Remove range mask.
            subnet -= min(range, max) * 32

            rangeaddr = addr.supernet(new_prefix=subnet).exploded.split('/', 1)[0]
            return rangeaddr.replace(':0000', ':*')
        except ValueError:
            pass

        # Host?
        if '.' in host:
            # Split pieces.
            pieces = host.split('.')
            max = len(pieces)
            if not allow_everything:
                max -= 1

            # Figure out how many to mask.
            to_mask = min(range, max)
            # Mask pieces.
            pieces[:to_mask] = '*' * to_mask
            return '.'.join(pieces)

        # Wat.
        if allow_everything and range >= 4:
            return '*'
        else:
            return host

    ## Connection.

    async def connect(self, hostname=None, port=None, password=None, **kwargs):
        port = port or protocol.DEFAULT_PORT

        # Connect...
        await super().connect(hostname, port, **kwargs)

        # Check if a password was provided and we don't already have one
        if password is not None and not self.password:
            # if so, set the password.
            self.password = password
        # And initiate the IRC connection.
        await self._register()

    async def _register(self):
        """ Perform IRC connection registration. """
        if self.registered:
            return
        self._registration_attempts += 1

        # Don't throttle during registration, most ircds don't care for flooding during registration,
        # and it might speed it up significantly.
        self.connection.throttle = False

        # Password first.
        if self.password:
            await self.rawmsg('PASS', self.password)

        # Then nickname...
        await self.set_nickname(self._attempt_nicknames.pop(0))
        # And now for the rest of the user information.
        await self.rawmsg('USER', self.username, '0', '*', self.realname)

    async def _registration_completed(self, message):
        """ We're connected and registered. Receive proper nickname and emit fake NICK message. """
        if not self.registered:
            # Re-enable throttling.
            self.registered = True
            self.connection.throttle = True

            target = message.params[0]
            fakemsg = self._create_message('NICK', target, source=self.nickname)
            await self.on_raw_nick(fakemsg)

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

    async def set_nickname(self, nickname):
        """
        Set nickname to given nickname.
        Users should only rely on the nickname actually being changed when receiving an on_nick_change callback.
        """
        await self.rawmsg('NICK', nickname)

    async def join(self, channel, password=None):
        """ Join channel, optionally with password. """
        if self.in_channel(channel):
            raise AlreadyInChannel(channel)

        if password:
            await self.rawmsg('JOIN', channel, password)
        else:
            await self.rawmsg('JOIN', channel)

    async def part(self, channel, message=None):
        """ Leave channel, optionally with message. """
        if not self.in_channel(channel):
            raise NotInChannel(channel)

        # Message seems to be an extension to the spec.
        if message:
            await self.rawmsg('PART', channel, message)
        else:
            await self.rawmsg('PART', channel)

    async def kick(self, channel, target, reason=None):
        """ Kick user from channel. """
        if not self.in_channel(channel):
            raise NotInChannel(channel)

        if reason:
            await self.rawmsg('KICK', channel, target, reason)
        else:
            await self.rawmsg('KICK', channel, target)

    async def ban(self, channel, target, range=0):
        """
        Ban user from channel. Target can be either a user or a host.
        This command will not kick: use kickban() for that.
        range indicates the IP/host range to ban: 0 means ban only the IP/host,
        1+ means ban that many 'degrees' (up to 3 for IP addresses) of the host for range bans.
        """
        if target in self.users:
            host = self.users[target]['hostname']
        else:
            host = target

        host = self._format_host_range(host, range)
        mask = self._format_host_mask('*', '*', host)
        await self.rawmsg('MODE', channel, '+b', mask)

    async def unban(self, channel, target, range=0):
        """
        Unban user from channel. Target can be either a user or a host.
        See ban documentation for the range parameter.
        """
        if target in self.users:
            host = self.users[target]['hostname']
        else:
            host = target

        host = self._format_host_range(host, range)
        mask = self._format_host_mask('*', '*', host)
        await self.rawmsg('MODE', channel, '-b', mask)

    async def kickban(self, channel, target, reason=None, range=0):
        """
        Kick and ban user from channel.
        """
        await self.ban(channel, target, range)
        await self.kick(channel, target, reason)

    async def quit(self, message=None):
        """ Quit network. """
        if message is None:
            message = self.DEFAULT_QUIT_MESSAGE

        await self.rawmsg('QUIT', message)
        await self.disconnect(expected=True)

    async def cycle(self, channel):
        """ Rejoin channel. """
        if not self.in_channel(channel):
            raise NotInChannel(channel)

        password = self.channels[channel]['password']
        await self.part(channel)
        await self.join(channel, password)

    async def message(self, target, message):
        """ Message channel or user. """
        hostmask = self._format_user_mask(self.nickname)
        # Leeway.
        chunklen = protocol.MESSAGE_LENGTH_LIMIT - len(
            '{hostmask} PRIVMSG {target} :'.format(hostmask=hostmask, target=target)) - 25

        for line in message.replace('\r', '').split('\n'):
            for chunk in chunkify(line, chunklen):
                # Some IRC servers respond with "412 Bot :No text to send" on empty messages.
                await self.rawmsg('PRIVMSG', target, chunk or ' ')

    async def notice(self, target, message):
        """ Notice channel or user. """
        hostmask = self._format_user_mask(self.nickname)
        # Leeway.
        chunklen = protocol.MESSAGE_LENGTH_LIMIT - len(
            '{hostmask} NOTICE {target} :'.format(hostmask=hostmask, target=target)) - 25

        for line in message.replace('\r', '').split('\n'):
            for chunk in chunkify(line, chunklen):
                await self.rawmsg('NOTICE', target, chunk)

    async def set_mode(self, target, *modes):
        """
        Set mode on target.
        Users should only rely on the mode actually being changed when receiving an on_{channel,user}_mode_change callback.
        """
        if self.is_channel(target) and not self.in_channel(target):
            raise NotInChannel(target)

        await self.rawmsg('MODE', target, *modes)

    async def set_topic(self, channel, topic):
        """
        Set topic on channel.
        Users should only rely on the topic actually being changed when receiving an on_topic_change callback.
        """
        if not self.is_channel(channel):
            raise ValueError('Not a channel: {}'.format(channel))
        elif not self.in_channel(channel):
            raise NotInChannel(channel)

        await self.rawmsg('TOPIC', channel, topic)

    async def away(self, message):
        """ Mark self as away. """
        await self.rawmsg('AWAY', message)

    async def back(self):
        """ Mark self as not away. """
        await self.rawmsg('AWAY')

    async def whois(self, nickname):
        """
        Return information about user.
        This is an blocking asynchronous method: it has to be called from a coroutine, as follows:

            info = await self.whois('Nick')
        """
        # Some IRCDs are wonky and send strange responses for spaces in nicknames.
        # We just check if there's a space in the nickname -- if there is,
        # then we immediately set the future's result to None and don't bother checking.
        if protocol.ARGUMENT_SEPARATOR.search(nickname) is not None:
            result = self.eventloop.create_future()
            result.set_result(None)
            return result

        if nickname not in self._pending['whois']:
            await self.rawmsg('WHOIS', nickname)
            self._whois_info[nickname] = {
                'oper': False,
                'idle': 0,
                'away': False,
                'away_message': None
            }

            # Create a future for when the WHOIS requests succeeds.
            self._pending['whois'][nickname] = self.eventloop.create_future()

        return await self._pending['whois'][nickname]

    async def whowas(self, nickname):
        """
        Return information about offline user.
        This is an blocking asynchronous method: it has to be called from a coroutine, as follows:

            info = await self.whowas('Nick')
        """
        # Same treatment as nicknames in whois.
        if protocol.ARGUMENT_SEPARATOR.search(nickname) is not None:
            result = self.eventloop.create_future()
            result.set_result(None)
            return result

        if nickname not in self._pending['whowas']:
            await self.rawmsg('WHOWAS', nickname)
            self._whowas_info[nickname] = {}

            # Create a future for when the WHOWAS requests succeeds.
            self._pending['whowas'][nickname] = self.eventloop.create_future()

        return await self._pending['whowas'][nickname]

    ## IRC helpers.

    def normalize(self, input):
        return parsing.normalize(input, case_mapping=self._case_mapping)

    def is_channel(self, chan):
        return any(chan.startswith(prefix) for prefix in self._channel_prefixes)

    def is_same_nick(self, left, right):
        """ Check if given nicknames are equal in the server's case mapping. """
        return self.normalize(left) == self.normalize(right)

    def is_same_channel(self, left, right):
        """ Check if given nicknames are equal in the server's case mapping. """
        return self.normalize(left) == self.normalize(right)

    ## Overloadable callbacks.

    async def on_connect(self):
        # Auto-join channels.
        for channel in self._autojoin_channels:
            await self.join(channel)

        # super call
        await super().on_connect()

    async def on_invite(self, channel, by):
        """ Callback called when the client was invited into a channel by someone. """
        pass

    async def on_user_invite(self, target, channel, by):
        """ Callback called when another user was invited into a channel by someone. """
        pass

    async def on_join(self, channel, user):
        """ Callback called when a user, possibly the client, has joined the channel. """
        pass

    async def on_kill(self, target, by, reason):
        """ Callback called when a user, possibly the client, was killed from the server. """
        pass

    async def on_kick(self, channel, target, by, reason=None):
        """ Callback called when a user, possibly the client, was kicked from a channel. """
        pass

    async def on_mode_change(self, channel, modes, by):
        """ Callback called when the mode on a channel was changed. """
        pass

    async def on_user_mode_change(self, modes):
        """ Callback called when a user mode change occurred for the client. """
        pass

    async def on_message(self, target, by, message):
        """ Callback called when the client received a message. """
        pass

    async def on_channel_message(self, target, by, message):
        """ Callback received when the client received a message in a channel. """
        pass

    async def on_private_message(self, target, by, message):
        """ Callback called when the client received a message in private. """
        pass

    async def on_nick_change(self, old, new):
        """ Callback called when a user, possibly the client, changed their nickname. """
        pass

    async def on_notice(self, target, by, message):
        """ Callback called when the client received a notice. """
        pass

    async def on_channel_notice(self, target, by, message):
        """ Callback called when the client received a notice in a channel. """
        pass

    async def on_private_notice(self, target, by, message):
        """ Callback called when the client received a notice in private. """
        pass

    async def on_part(self, channel, user, message=None):
        """ Callback called when a user, possibly the client, left a channel. """
        pass

    async def on_topic_change(self, channel, message, by):
        """ Callback called when the topic for a channel was changed. """
        pass

    async def on_quit(self, user, message=None):
        """ Callback called when a user, possibly the client, left the network. """
        pass

    ## Callback handlers.

    async def on_raw_error(self, message):
        """ Server encountered an error and will now close the connection. """
        error = protocol.ServerError(' '.join(message.params))
        await self.on_data_error(error)

    async def on_raw_pong(self, message):
        self.logger.debug('>> PONG received')

    async def on_raw_invite(self, message):
        """ INVITE command. """
        nick, metadata = self._parse_user(message.source)
        self._sync_user(nick, metadata)

        target, channel = message.params
        target, metadata = self._parse_user(target)

        if self.is_same_nick(self.nickname, target):
            await self.on_invite(channel, nick)
        else:
            await self.on_user_invite(target, channel, nick)

    async def on_raw_join(self, message):
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
                await self.rawmsg('MODE', channel)
        else:
            # Add user to channel user list.
            for channel in channels:
                if self.in_channel(channel):
                    self.channels[channel]['users'].add(nick)

        for channel in channels:
            await self.on_join(channel, nick)

    async def on_raw_kick(self, message):
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

        for channel, target in itertools.product(channels, targets):
            target, targetmeta = self._parse_user(target)
            self._sync_user(target, targetmeta)

            if self.is_same_nick(target, self.nickname):
                self._destroy_channel(channel)
            else:
                # Update nick list on channel.
                if self.in_channel(channel):
                    self._destroy_user(target, channel)

            await self.on_kick(channel, target, kicker, reason)

    async def on_raw_kill(self, message):
        """ KILL command. """
        by, bymeta = self._parse_user(message.source)
        target, targetmeta = self._parse_user(message.params[0])
        reason = message.params[1]

        self._sync_user(target, targetmeta)
        if by in self.users:
            self._sync_user(by, bymeta)

        await self.on_kill(target, by, reason)
        if self.is_same_nick(self.nickname, target):
            await self.disconnect(expected=False)
        else:
            self._destroy_user(target)

    async def on_raw_mode(self, message):
        """ MODE command. """
        nick, metadata = self._parse_user(message.source)
        target, modes = message.params[0], message.params[1:]

        self._sync_user(nick, metadata)
        if self.is_channel(target):
            if self.in_channel(target):
                # Parse modes.
                self.channels[target]['modes'] = self._parse_channel_modes(target, modes)

                await self.on_mode_change(target, modes, nick)
        else:
            target, targetmeta = self._parse_user(target)
            self._sync_user(target, targetmeta)

            # Update own modes.
            if self.is_same_nick(self.nickname, nick):
                self._mode = self._parse_user_modes(nick, modes, current=self._mode)

            await self.on_user_mode_change(modes)

    async def on_raw_nick(self, message):
        """ NICK command. """
        nick, metadata = self._parse_user(message.source)
        new = message.params[0]

        self._sync_user(nick, metadata)
        # Acknowledgement of nickname change: set it internally, too.
        # Alternatively, we were force nick-changed. Nothing much we can do about it.
        if self.is_same_nick(self.nickname, nick):
            self.nickname = new

        # Go through all user lists and replace.
        self._rename_user(nick, new)

        # Call handler.
        await self.on_nick_change(nick, new)

    async def on_raw_notice(self, message):
        """ NOTICE command. """
        nick, metadata = self._parse_user(message.source)
        target, message = message.params

        self._sync_user(nick, metadata)

        await self.on_notice(target, nick, message)
        if self.is_channel(target):
            await self.on_channel_notice(target, nick, message)
        else:
            await self.on_private_notice(target, nick, message)

    async def on_raw_part(self, message):
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
                    await self.on_part(channel, nick, reason)
                    self._destroy_channel(channel)
        else:
            # Someone else left. Remove them.
            for channel in channels:
                await self.on_part(channel, nick, reason)
                self._destroy_user(nick, channel)

    async def on_raw_ping(self, message):
        """ PING command. """
        # Respond with a pong.
        await self.rawmsg('PONG', *message.params)

    async def on_raw_privmsg(self, message):
        """ PRIVMSG command. """
        nick, metadata = self._parse_user(message.source)
        target, message = message.params

        self._sync_user(nick, metadata)

        await self.on_message(target, nick, message)
        if self.is_channel(target):
            await self.on_channel_message(target, nick, message)
        else:
            await self.on_private_message(target, nick, message)

    async def on_raw_quit(self, message):
        """ QUIT command. """
        nick, metadata = self._parse_user(message.source)

        self._sync_user(nick, metadata)
        if message.params:
            reason = message.params[0]
        else:
            reason = None

        await self.on_quit(nick, reason)
        # Remove user from database.
        if not self.is_same_nick(self.nickname, nick):
            self._destroy_user(nick)
        # Else, we quit.
        elif self.connected:
            await self.disconnect(expected=True)

    async def on_raw_topic(self, message):
        """ TOPIC command. """
        setter, settermeta = self._parse_user(message.source)
        target, topic = message.params

        self._sync_user(setter, settermeta)

        # Update topic in our own channel list.
        if self.in_channel(target):
            self.channels[target]['topic'] = topic
            self.channels[target]['topic_by'] = setter
            self.channels[target]['topic_set'] = datetime.datetime.now()

        await self.on_topic_change(target, topic, setter)

    ## Numeric responses.

    # Since RFC1459 specifies no specific banner message upon completion of registration,
    # take any of the below commands as an indication that registration succeeded.

    on_raw_001 = _registration_completed  # Welcome message.
    on_raw_002 = _registration_completed  # Server host.
    on_raw_003 = _registration_completed  # Server creation time.

    async def on_raw_004(self, message):
        """ Basic server information. """
        target, hostname, ircd, user_modes, channel_modes = message.params[:5]

        # Set valid channel and user modes.
        self._channel_modes = set(channel_modes)
        self._user_modes = set(user_modes)

    on_raw_008 = _registration_completed  # Server notice mask.
    on_raw_042 = _registration_completed  # Unique client ID.
    on_raw_250 = _registration_completed  # Connection statistics.
    on_raw_251 = _registration_completed  # Amount of users online.
    on_raw_252 = _registration_completed  # Amount of operators online.
    on_raw_253 = _registration_completed  # Amount of unknown connections.
    on_raw_254 = _registration_completed  # Amount of channels.
    on_raw_255 = _registration_completed  # Amount of local users and servers.
    on_raw_265 = _registration_completed  # Amount of local users.
    on_raw_266 = _registration_completed  # Amount of global users.

    async def on_raw_301(self, message):
        """ User is away. """
        target, nickname, message = message.params
        info = {
            'away': True,
            'away_message': message
        }

        if nickname in self.users:
            self._sync_user(nickname, info)
        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_311(self, message):
        """ WHOIS user info. """
        target, nickname, username, hostname, _, realname = message.params
        info = {
            'username': username,
            'hostname': hostname,
            'realname': realname
        }

        self._sync_user(nickname, info)
        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_312(self, message):
        """ WHOIS server info. """
        target, nickname, server, serverinfo = message.params
        info = {
            'server': server,
            'server_info': serverinfo
        }

        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)
        if nickname in self._pending['whowas']:
            self._whowas_info[nickname].update(info)

    async def on_raw_313(self, message):
        """ WHOIS operator info. """
        target, nickname = message.params[:2]
        info = {
            'oper': True
        }

        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_314(self, message):
        """ WHOWAS user info. """
        target, nickname, username, hostname, _, realname = message.params
        info = {
            'username': username,
            'hostname': hostname,
            'realname': realname
        }

        if nickname in self._pending['whowas']:
            self._whowas_info[nickname].update(info)

    on_raw_315 = BasicClient._ignored  # End of /WHO list.

    async def on_raw_317(self, message):
        """ WHOIS idle time. """
        target, nickname, idle_time = message.params[:3]
        info = {
            'idle': int(idle_time),
        }

        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_318(self, message):
        """ End of /WHOIS list. """
        target, nickname = message.params[:2]

        # Mark future as done.
        if nickname in self._pending['whois']:
            future = self._pending['whois'].pop(nickname)
            future.set_result(self._whois_info[nickname])

    async def on_raw_319(self, message):
        """ WHOIS active channels. """
        target, nickname, channels = message.params[:3]
        channels = {channel.lstrip() for channel in channels.strip().split(' ')}
        info = {
            'channels': channels
        }

        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_324(self, message):
        """ Channel mode. """
        target, channel = message.params[:2]
        modes = message.params[2:]
        if not self.in_channel(channel):
            return

        self.channels[channel]['modes'] = self._parse_channel_modes(channel, modes)

    async def on_raw_329(self, message):
        """ Channel creation time. """
        target, channel, timestamp = message.params
        if not self.in_channel(channel):
            return

        self.channels[channel]['created'] = datetime.datetime.fromtimestamp(int(timestamp))

    async def on_raw_332(self, message):
        """ Current topic on channel join. """
        target, channel, topic = message.params
        if not self.in_channel(channel):
            return

        self.channels[channel]['topic'] = topic

    async def on_raw_333(self, message):
        """ Topic setter and time on channel join. """
        target, channel, setter, timestamp = message.params
        if not self.in_channel(channel):
            return

        # No need to sync user since this is most likely outdated info.
        self.channels[channel]['topic_by'] = self._parse_user(setter)[0]
        self.channels[channel]['topic_set'] = datetime.datetime.fromtimestamp(int(timestamp))

    async def on_raw_353(self, message):
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
        for entry in names.split(' '):
            statuses = []
            # Make entry safe for _parse_user().
            safe_entry = entry.lstrip(''.join(self._nickname_prefixes.keys()))
            # Parse entry and update database.
            nick, metadata = self._parse_user(safe_entry)
            if not nick:
                # nonsense nickname
                continue
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

    on_raw_366 = BasicClient._ignored  # End of /NAMES list.

    async def on_raw_375(self, message):
        """ Start message of the day. """
        await self._registration_completed(message)
        self.motd = message.params[1] + '\n'

    async def on_raw_372(self, message):
        """ Append message of the day. """
        self.motd += message.params[1] + '\n'

    async def on_raw_376(self, message):
        """ End of message of the day. """
        self.motd += message.params[1] + '\n'

        # MOTD is done, let's tell our bot the connection is ready.
        await self.on_connect()

    async def on_raw_401(self, message):
        """ No such nick/channel. """
        nickname = message.params[1]

        # Remove nickname from whois requests if it involves one of ours.
        if nickname in self._pending['whois']:
            future = self._pending['whois'].pop(nickname)
            future.set_result(None)
            del self._whois_info[nickname]

    async def on_raw_402(self, message):
        """ No such server. """
        return await self.on_raw_401(message)

    async def on_raw_422(self, message):
        """ MOTD is missing. """
        await self._registration_completed(message)
        self.motd = None
        await self.on_connect()

    async def on_raw_421(self, message):
        """ Server responded with 'unknown command'. """
        self.logger.warning('Server responded with "Unknown command: %s"', message.params[0])

    async def on_raw_432(self, message):
        """ Erroneous nickname. """
        if not self.registered:
            # Nothing else we can do than try our next nickname.
            await self.on_raw_433(message)

    async def on_raw_433(self, message):
        """ Nickname in use. """
        if not self.registered:
            self._registration_attempts += 1
            # Attempt to set new nickname.
            if self._attempt_nicknames:
                await self.set_nickname(self._attempt_nicknames.pop(0))
            else:
                await self.set_nickname(
                    self._nicknames[0] + '_' * (self._registration_attempts - len(self._nicknames)))

    on_raw_436 = BasicClient._ignored  # Nickname collision, issued right before the server kills us.

    async def on_raw_451(self, message):
        """ We have to register first before doing X. """
        self.logger.warning('Attempted to send non-registration command before being registered.')

    on_raw_451 = BasicClient._ignored  # You have to register first.
    on_raw_462 = BasicClient._ignored  # You may not re-register.


## Helpers.

def chunkify(message, chunksize):
    if not message:
        yield message
    else:
        while message:
            chunk = message[:chunksize]
            message = message[chunksize:]
            yield chunk
