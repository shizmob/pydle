## whox.py
# WHOX support.
from pydle.features import isupport, account

NO_ACCOUNT = '0'
# Maximum of 3 characters because Charybdis stupidity. The ASCII values of 'pydle' added together.
WHOX_IDENTIFIER = '542'

class WHOXSupport(isupport.ISUPPORTSupport, account.AccountSupport):

    ## Overrides.

    def on_raw_join(self, message):
        """ Override JOIN to send WHOX. """
        super().on_raw_join(message)
        user = self._parse_and_sync_user(message.source)
        channels = message.params[0].split(',')

        if self.is_same_nick(self.nickname, user.nickname):
            # We joined.
            if 'WHOX' in self._isupport and self._isupport['WHOX']:
                # Get more relevant channel info thanks to WHOX.
                self.rawmsg('WHO', ','.join(channels), '%tnurha,{id}'.format(id=WHOX_IDENTIFIER))
        else:
            # Find account name of person.
            pass

    def on_raw_354(self, message):
        """ WHOX results have arrived. """
        # Is the message for us?
        target, identifier = message.params[:2]
        if identifier != WHOX_IDENTIFIER:
            return

        # Great. Extract relevant information.
        user = self._get_user(message.params[4])
        user.username = message.params[2]
        user.realname = message.params[6]
        user.hostname = message.params[3]
        user.account = message.params[5] if message.params[5] != NO_ACCOUNT else None
