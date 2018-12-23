## isupport.py
# ISUPPORT (server-side IRC extension indication) support.
# See: http://tools.ietf.org/html/draft-hardy-irc-isupport-00
import collections
import pydle.protocol
from pydle.features import rfc1459

__all__ = [ 'ISUPPORTSupport' ]


FEATURE_DISABLED_PREFIX = '-'
BAN_EXCEPT_MODE = 'e'
INVITE_EXCEPT_MODE = 'I'


class ISUPPORTSupport(rfc1459.RFC1459Support):
    """ ISUPPORT support. """

    ## Internal overrides.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._isupport = {}
        self._extban_types = []
        self._extban_prefix = None

    def _create_channel(self, channel):
        """ Create channel with optional ban and invite exception lists. """
        super()._create_channel(channel)
        if 'EXCEPTS' in self._isupport:
            self.channels[channel]['exceptlist'] = None
        if 'INVEX' in self._isupport:
            self.channels[channel]['inviteexceptlist'] = None


    ## Command handlers.

    async def on_raw_005(self, message):
        """ ISUPPORT indication. """
        isupport = {}

        # Parse response.
        # Strip target (first argument) and 'are supported by this server' (last argument).
        for feature in message.params[1:-1]:
            if feature.startswith(FEATURE_DISABLED_PREFIX):
                value = False
            elif '=' in feature:
                feature, value = feature.split('=', 1)
            else:
                value = True
            isupport[feature.upper()] = value

        # Update internal dict first.
        self._isupport.update(isupport)

        # And have callbacks update other internals.
        for entry, value in isupport.items():
            if value != False:
                # A value of True technically means there was no value supplied; correct this for callbacks.
                if value == True:
                    value = None

                method = 'on_isupport_' + pydle.protocol.identifierify(entry)
                if hasattr(self, method):
                    await getattr(self, method)(value)


    ## ISUPPORT handlers.

    async def on_isupport_awaylen(self, value):
        """ Away message length limit. """
        self._away_message_length_limit = int(value)

    async def on_isupport_casemapping(self, value):
        """ IRC case mapping for nickname and channel name comparisons. """
        if value in rfc1459.protocol.CASE_MAPPINGS:
            self._case_mapping = value
            self.channels = rfc1459.parsing.NormalizingDict(self.channels, case_mapping=value)
            self.users = rfc1459.parsing.NormalizingDict(self.users, case_mapping=value)

    async def on_isupport_channellen(self, value):
        """ Channel name length limit. """
        self._channel_length_limit = int(value)

    async def on_isupport_chanlimit(self, value):
        """ Simultaneous channel limits for user. """
        self._channel_limits = {}

        for entry in value.split(','):
            types, limit = entry.split(':')

            # Assign limit to channel type group and add lookup entry for type.
            self._channel_limits[frozenset(types)] = int(limit)
            for prefix in types:
                self._channel_limit_groups[prefix] = frozenset(types)

    async def on_isupport_chanmodes(self, value):
        """ Valid channel modes and their behaviour. """
        list, param, param_set, noparams = [ set(modes) for modes in value.split(',')[:4] ]
        self._channel_modes.update(set(value.replace(',', '')))

        # The reason we have to do it like this is because other ISUPPORTs (e.g. PREFIX) may update these values as well.
        if not rfc1459.protocol.BEHAVIOUR_LIST in self._channel_modes_behaviour:
            self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_LIST] = set()
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_LIST].update(list)

        if not rfc1459.protocol.BEHAVIOUR_PARAMETER in self._channel_modes_behaviour:
            self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER] = set()
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER].update(param)

        if not rfc1459.protocol.BEHAVIOUR_PARAMETER_ON_SET in self._channel_modes_behaviour:
            self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER_ON_SET] = set()
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER_ON_SET].update(param_set)

        if not rfc1459.protocol.BEHAVIOUR_NO_PARAMETER in self._channel_modes_behaviour:
            self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_NO_PARAMETER] = set()
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_NO_PARAMETER].update(noparams)

    async def on_isupport_chantypes(self, value):
        """ Channel name prefix symbols. """
        if not value:
            value = ''
        self._channel_prefixes = set(value)

    async def on_isupport_excepts(self, value):
        """ Server allows ban exceptions. """
        if not value:
            value = BAN_EXCEPT_MODE
        self._channel_modes.add(value)
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_LIST].add(value)

    async def on_isupport_extban(self, value):
        """ Extended ban prefixes. """
        self._extban_prefix, types = value.split(',')
        self._extban_types = set(types)

    async def on_isupport_invex(self, value):
        """ Server allows invite exceptions. """
        if not value:
            value = INVITE_EXCEPT_MODE
        self._channel_modes.add(value)
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_LIST].add(value)

    async def on_isupport_maxbans(self, value):
        """ Maximum entries in ban list. Replaced by MAXLIST. """
        if 'MAXLIST' not in self._isupport:
            if not self._list_limits:
                self._list_limits = {}
            self._list_limits['b'] = int(value)

    async def on_isupport_maxchannels(self, value):
        """ Old version of CHANLIMIT. """
        if 'CHANTYPES' in self._isupport and 'CHANLIMIT' not in self._isupport:
            self._channel_limits = {}

            prefixes = self._isupport['CHANTYPES']
            # Assume the limit is for all types of channels. Make a single group for all types.
            self._channel_limits[frozenset(prefixes)] = int(value)
            for prefix in prefixes:
                self._channel_limit_groups[prefix] = frozenset(prefixes)

    async def on_isupport_maxlist(self, value):
        """ Limits on channel modes involving lists. """
        self._list_limits = {}

        for entry in value.split(','):
            modes, limit = entry.split(':')

            # Assign limit to mode group and add lookup entry for mode.
            self._list_limits[frozenset(modes)] = int(limit)
            for mode in modes:
                self._list_limit_groups[mode] = frozenset(modes)

    async def on_isupport_maxpara(self, value):
        """ Limits to parameters given to command. """
        self._command_parameter_limit = int(value)

    async def on_isupport_modes(self, value):
        """ Maximum number of variable modes to change in a single MODE command. """
        self._mode_limit = int(value)

    async def on_isupport_namesx(self, value):
        """ Let the server know we do in fact support NAMESX. Effectively the same as CAP multi-prefix. """
        await self.rawmsg('PROTOCTL', 'NAMESX')

    async def on_isupport_network(self, value):
        """ IRC network name. """
        self.network = value

    async def on_isupport_nicklen(self, value):
        """ Nickname length limit. """
        self._nickname_length_limit = int(value)

    async def on_isupport_prefix(self, value):
        """ Nickname prefixes on channels and their associated modes. """
        if not value:
            # No prefixes support.
            self._nickname_prefixes = collections.OrderedDict()
            return

        modes, prefixes = value.lstrip('(').split(')', 1)

        # Update valid channel modes and their behaviour as CHANMODES doesn't include PREFIX modes.
        self._channel_modes.update(set(modes))
        if not rfc1459.protocol.BEHAVIOUR_PARAMETER in self._channel_modes_behaviour:
            self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER] = set()
        self._channel_modes_behaviour[rfc1459.protocol.BEHAVIOUR_PARAMETER].update(set(modes))

        self._nickname_prefixes = collections.OrderedDict()
        for mode, prefix in zip(modes, prefixes):
            self._nickname_prefixes[prefix] = mode

    async def on_isupport_statusmsg(self, value):
        """ Support for messaging every member on a channel with given status or higher. """
        self._status_message_prefixes.update(value)

    async def on_isupport_targmax(self, value):
        """ The maximum number of targets certain types of commands can affect. """
        if not value:
            return

        for entry in value.split(','):
            command, limit = entry.split(':', 1)
            if not limit:
                continue
            self._target_limits[command] = int(limit)

    async def on_isupport_topiclen(self, value):
        """ Channel topic length limit. """
        self._topic_length_limit = int(value)

    async def on_isupport_wallchops(self, value):
        """ Support for messaging every opped member or higher on a channel. Replaced by STATUSMSG. """
        for prefix, mode in self._nickname_prefixes.items():
            if mode == 'o':
                break
        else:
            prefix = '@'
        self._status_message_prefixes.add(prefix)

    async def on_isupport_wallvoices(self, value):
        """ Support for messaging every voiced member or higher on a channel. Replaced by STATUSMSG. """
        for prefix, mode in self._nickname_prefixes.items():
            if mode == 'v':
                break
        else:
            prefix = '+'
        self._status_message_prefixes.add(prefix)
