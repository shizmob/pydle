## account.py
# Account system support.
from pydle.features import rfc1459
import asyncio

class AccountSupport(rfc1459.RFC1459Support):

    ## Internal.

    def _create_user(self, nickname):
        super()._create_user(nickname)
        if nickname in self.users:
            self.users[nickname].update({
                'account': None,
                'identified': False
            })

    def _rename_user(self, user, new):
        super()._rename_user(user, new)
        # Unset account info to be certain until we get a new response.
        self._sync_user(new, {'account': None, 'identified': False})
        self.whois(new)

    ## IRC API.
    @asyncio.coroutine
    def whois(self, nickname):
        info = yield from super().whois(nickname)
        info.setdefault('account', None)
        info.setdefault('identified', False)
        return info

    ## Message handlers.

    async def on_raw_307(self, message):
        """ WHOIS: User has identified for this nickname. (Anope) """
        target, nickname = message.params[:2]
        info = {
            'identified': True
        }

        if nickname in self.users:
            self._sync_user(nickname, info)
        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)

    async def on_raw_330(self, message):
        """ WHOIS account name (Atheme). """
        target, nickname, account = message.params[:3]
        info = {
            'account': account,
            'identified': True
        }

        if nickname in self.users:
            self._sync_user(nickname, info)
        if nickname in self._pending['whois']:
            self._whois_info[nickname].update(info)
