## ircv3_2.py
# IRCv3.2 support (in progress).
from . import ircv3_1
from . import tags
from . import monitor
from . import metadata

__all__ = [ 'IRCv3_2Support' ]


class IRCv3_2Support(metadata.MetadataSupport, monitor.MonitoringSupport, tags.TaggedMessageSupport, ircv3_1.IRCv3_1Support):
    """ Support for some of IRCv3.2's extensions. Currently supported: chghost, userhost-in-names. """

    ## IRC callbacks.
    def on_capability_cap_notify_available(self, value):
        """ Take note of new or removed capabilities. """
        return True
    
    def on_capability_chghost_available(self, value):
        """ Server reply to indicate a user we are in a common channel with changed user and/or host. """
        return True

    def on_capability_userhost_in_names_available(self, value):
        """ Show full user!nick@host in NAMES list. We already parse it like that. """
        return True

    def on_capability_uhnames_available(self, value):
        """ Possibly outdated alias for userhost-in-names. """
        return self.on_capability_userhost_in_names_available(value)

    def on_isupport_uhnames(self, value):
        """ Let the server know that we support UHNAMES using the old ISUPPORT method, for legacy support. """
        self.rawmsg('PROTOCTL', 'UHNAMES')


    ## Message handlers.

    def on_raw_chghost(self, message):
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
