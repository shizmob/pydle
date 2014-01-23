## ircv3_2.py
# IRCv3.2 support (in progress).
from .. import client
from .. import protocol

from . import isupport
from . import cap

__all__ = [ 'IRCv3_2Support' ]


class IRCv3_2Support(cap.CapabilityNegotiationSupport, isupport.ISUPPORTSupport):
    """ Support for some of IRCv3.2's extensions. Currently supported: chghost, userhost-in-names. """

    ## IRC callbacks.

    def on_capability_chghost_available(self):
        """ Server reply to indicate a user we are in a common channel with changed user and/or host. """
        return True

    def on_capability_userhost_in_names_available(self):
        """ Show full user!nick@host in NAMES list. We already parse it like that. """
        return True

    def on_capability_uhnames_available(self):
        """ Possibly outdated alias for userhost-in-names. """
        return self.on_capability_userhost_in_names_available()

    def on_isupport_uhnames(self, value):
        """ Let the server know that we support UHNAMES using the old ISUPPORT method, for legacy support. """
        self.rawmsg('PROTOCTL', 'UHNAMES')


    ## Message handlers.

    def on_raw_chghost(self, source, params):
        """ Change user and/or host of user. """
        if 'chghost' not in self._capabilities or not self._capabilities['chghost']:
            return

        nick = protocol.parse_user(source)[0]
        if nick not in self.users:
            return

        # Update user and host.
        user, host = params
        if self.is_same_nick(self.nickname, nick):
            self.username = user
            self.hostname = host
        else:
            self.users[nick]['username'] = user
            self.users[nick]['hostname'] = host
