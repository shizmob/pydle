## ircv3_1.py
# IRCv3.1 full spec support.
from pydle.features import account, tls
from . import cap
from . import sasl

__all__ = [ 'IRCv3_1Support' ]


NO_ACCOUNT = '*'

class IRCv3_1Support(sasl.SASLSupport, cap.CapabilityNegotiationSupport, account.AccountSupport, tls.TLSSupport):
    """ Support for IRCv3.1's base and optional extensions. """

    ## IRC callbacks.

    def on_capability_account_notify_available(self, value):
        """ Take note of user account changes. """
        return True

    def on_capability_away_notify_available(self, value):
        """ Take note of AWAY messages. """
        return True

    def on_capability_extended_join_available(self, value):
        """ Take note of user account and realname on JOIN. """
        return True

    def on_capability_multi_prefix_available(self, value):
        """ Thanks to how underlying client code works we already support multiple prefixes. """
        return True

    def on_capability_tls_available(self, value):
        """ We never need to request this explicitly. """
        return False


    ## Message handlers.

    def on_raw_account(self, message):
        """ Changes in the associated account for a nickname. """
        if 'account-notify' not in self._capabilities or not self._capabilities['account-notify']:
            return

        user = self._parse_and_sync_user(message.source)
        account = message.params[0]
        if account != NO_ACCOUNT:
            user.account = account
            user.identified = True

    def on_raw_away(self, message):
        """ Process AWAY messages. """
        if 'away-notify' not in self._capabilities or not self._capabilities['away-notify']:
            return

        user = self._parse_and_syn_user(message.source)
        user.away_message = message.params[0] if len(message.params) > 0 else None

    def on_raw_join(self, message):
        """ Process extended JOIN messages. """
        if 'extended-join' in self._capabilities and self._capabilities['extended-join']:
            user = self._parse_and_sync_user(message.source)
            channels, account, realname = message.params

            # Emit a fake join message.
            fakemsg = self._create_message('JOIN', channels, source=message.source)
            super().on_raw_join(fakemsg)

            if account == NO_ACCOUNT:
                account = None
            user.account = account
            user.identified = user.account is not None
            user.realname = realname
        else:
            super().on_raw_join(message)
