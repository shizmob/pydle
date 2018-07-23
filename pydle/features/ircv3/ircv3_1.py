## ircv3_1.py
# IRCv3.1 full spec support.
from pydle.features import account, tls
from . import cap
from . import sasl

__all__ = [ 'IRCv3_1Support' ]


NO_ACCOUNT = '*'

class IRCv3_1Support(sasl.SASLSupport, cap.CapabilityNegotiationSupport, account.AccountSupport, tls.TLSSupport):
    """ Support for IRCv3.1's base and optional extensions. """

    def _rename_user(self, user, new):
        # If the server supports account-notify, we will be told about the registration status changing.
        # As such, we can skip the song and dance pydle.features.account does.
        if self._capabilities.get('account-notify', False):
            account = self.users.get(user, {}).get('account', None)
            identified = self.users.get(user, {}).get('identified', False)

        super()._rename_user(user, new)

        if self._capabilities.get('account-notify', False):
            self._sync_user(new, {'account': account, 'identified': identified})

    ## IRC callbacks.

    async def on_capability_account_notify_available(self, value):
        """ Take note of user account changes. """
        return True

    async def on_capability_away_notify_available(self, value):
        """ Take note of AWAY messages. """
        return True

    async def on_capability_extended_join_available(self, value):
        """ Take note of user account and realname on JOIN. """
        return True

    async def on_capability_multi_prefix_available(self, value):
        """ Thanks to how underlying client code works we already support multiple prefixes. """
        return True

    async def on_capability_tls_available(self, value):
        """ We never need to request this explicitly. """
        return False


    ## Message handlers.

    async def on_raw_account(self, message):
        """ Changes in the associated account for a nickname. """
        if not self._capabilities.get('account-notify', False):
            return

        nick, metadata = self._parse_user(message.source)
        account = message.params[0]

        if nick not in self.users:
            return

        self._sync_user(nick, metadata)
        if account == NO_ACCOUNT:
            self._sync_user(nick, { 'account': None, 'identified': False })
        else:
            self._sync_user(nick, { 'account': account, 'identified': True })

    async def on_raw_away(self, message):
        """ Process AWAY messages. """
        if 'away-notify' not in self._capabilities or not self._capabilities['away-notify']:
            return

        nick, metadata = self._parse_user(message.source)
        if nick not in self.users:
            return

        self._sync_user(nick, metadata)
        self.users[nick]['away'] = len(message.params) > 0
        self.users[nick]['away_message'] = message.params[0] if len(message.params) > 0 else None

    async def on_raw_join(self, message):
        """ Process extended JOIN messages. """
        if 'extended-join' in self._capabilities and self._capabilities['extended-join']:
            nick, metadata = self._parse_user(message.source)
            channels, account, realname = message.params

            self._sync_user(nick, metadata)

            # Emit a fake join message.
            fakemsg = self._create_message('JOIN', channels, source=message.source)
            await super().on_raw_join(fakemsg)

            if account == NO_ACCOUNT:
                account = None
            self.users[nick]['account'] = account
            self.users[nick]['realname'] = realname
        else:
            await super().on_raw_join(message)
