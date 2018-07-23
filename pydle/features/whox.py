## whox.py
# WHOX support.
from pydle.features import isupport, account

NO_ACCOUNT = '0'
# Maximum of 3 characters because Charybdis stupidity. The ASCII values of 'pydle' added together.
WHOX_IDENTIFIER = '542'

class WHOXSupport(isupport.ISUPPORTSupport, account.AccountSupport):

    ## Overrides.

    async def on_raw_join(self, message):
        """ Override JOIN to send WHOX. """
        await super().on_raw_join(message)
        nick, metadata = self._parse_user(message.source)
        channels = message.params[0].split(',')

        if self.is_same_nick(self.nickname, nick):
            # We joined.
            if 'WHOX' in self._isupport and self._isupport['WHOX']:
                # Get more relevant channel info thanks to WHOX.
                await self.rawmsg('WHO', ','.join(channels), '%tnurha,{id}'.format(id=WHOX_IDENTIFIER))
        else:
            # Find account name of person.
            pass
    
    def _create_user(self, nickname):
        super()._create_user(nickname)
        if self.registered and 'WHOX' not in self._isupport:
            self.whois(nickname)

    async def on_raw_354(self, message):
        """ WHOX results have arrived. """
        # Is the message for us?
        target, identifier = message.params[:2]
        if identifier != WHOX_IDENTIFIER:
            return

        # Great. Extract relevant information.
        metadata = {
            'nickname': message.params[4],
            'username': message.params[2],
            'realname': message.params[6],
            'hostname': message.params[3],
        }
        if message.params[5] != NO_ACCOUNT:
            metadata['identified'] = True
            metadata['account'] = message.params[5]

        self._sync_user(metadata['nickname'], metadata)
