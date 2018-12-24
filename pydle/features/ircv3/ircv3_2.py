## ircv3_2.py
# IRCv3.2 support (in progress).
from . import ircv3_1
from . import tags
from . import monitor
from . import metadata

__all__ = [ 'IRCv3_2Support' ]


class IRCv3_2Support(metadata.MetadataSupport, monitor.MonitoringSupport, tags.TaggedMessageSupport, ircv3_1.IRCv3_1Support):
    """ Support for some of IRCv3.2's extensions. """

    ## IRC callbacks.

    async def on_capability_account_tag_available(self, value):
        """ Add an account message tag to user messages. """
        return True

    async def on_capability_cap_notify_available(self, value):
        """ Take note of new or removed capabilities. """
        return True
    
    async def on_capability_chghost_available(self, value):
        """ Server reply to indicate a user we are in a common channel with changed user and/or host. """
        return True

    async def on_capability_echo_message_available(self, value):
        """ Echo PRIVMSG and NOTICEs back to client. """
        return True

    async def on_capability_invite_notify_available(self, value):
        """ Broadcast invite messages to certain other clients. """
        return True

    async def on_capability_userhost_in_names_available(self, value):
        """ Show full user!nick@host in NAMES list. We already parse it like that. """
        return True

    async def on_capability_uhnames_available(self, value):
        """ Possibly outdated alias for userhost-in-names. """
        return await self.on_capability_userhost_in_names_available(value)

    async def on_isupport_uhnames(self, value):
        """ Let the server know that we support UHNAMES using the old ISUPPORT method, for legacy support. """
        await self.rawmsg('PROTOCTL', 'UHNAMES')



    ## API overrides.

    async def message(self, target, message):
        await super().message(target, message)
        if not self._capabilities.get('echo-message'):
            await self.on_message(target, self.nickname, message)
            if self.is_channel(target):
                await self.on_channel_message(target, self.nickname, message)
            else:
                await self.on_private_message(target, self.nickname, message)

    async def notice(self, target, message):
        await super().notice(target, message)
        if not self._capabilities.get('echo-message'):
            await self.on_notice(target, self.nickname, message)
            if self.is_channel(target):
                await self.on_channel_notice(target, self.nickname, message)
            else:
                await self.on_private_notice(target, self.nickname, message)


    ## Message handlers.

    async def on_raw(self, message):
        if 'account' in message.tags:
            nick, _ = self._parse_user(message.source)
            if nick in self.users:
                metadata = {
                    'identified': True,
                    'account': message.tags['account']
                }
                self._sync_user(nick, metadata)
        await super().on_raw(message)

    async def on_raw_chghost(self, message):
        """ Change user and/or host of user. """
        if 'chghost' not in self._capabilities or not self._capabilities['chghost']:
            return

        nick, _ = self._parse_user(message.source)
        if nick not in self.users:
            return

        # Update user and host.
        metadata = {
            'username': message.params[0],
            'hostname': message.params[1]
        }
        self._sync_user(nick, metadata)
