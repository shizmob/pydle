## monitor.py
# Online status monitoring support.
from .. import isupport


class MonitoringSupport(isupport.ISUPPORTSupport):
    """ Support for monitoring the online/offline status of certain targets. """

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._monitoring = set()

    def _destroy_user(self, nickname, channel=None, monitor_override=False):
        # Override _destroy_user to not remove user if they are being monitored by us.
        if channel:
            channels = [self.channels[channel]]
        else:
            channels = self.channels.values()

        for ch in channels:
            # Remove from nicklist.
            ch['users'].discard(nickname)

            # Remove from statuses.
            for status in self._nickname_prefixes.values():
                if status in ch['modes'] and nickname in ch['modes'][status]:
                    ch['modes'][status].remove(nickname)

        # If we're not in any common channels with the user anymore, we have no reliable way to keep their info up-to-date.
        # Remove the user.
        if (monitor_override or not self.is_monitoring(nickname)) and (not channel or not any(nickname in ch['users'] for ch in self.channels.values())):
            del self.users[nickname]

    ## API.

    async def monitor(self, target):
        """ Start monitoring the online status of a user. Returns whether or not the server supports monitoring. """
        if 'MONITOR' in self._isupport and not self.is_monitoring(target):
            await self.rawmsg('MONITOR', '+', target)
            self._monitoring.add(target)
            return True
        return False

    async def unmonitor(self, target):
        """ Stop monitoring the online status of a user. Returns whether or not the server supports monitoring. """
        if 'MONITOR' in self._isupport and self.is_monitoring(target):
            await self.rawmsg('MONITOR', '-', target)
            self._monitoring.remove(target)
            return True
        return False

    def is_monitoring(self, target):
        """ Return whether or not we are monitoring the target's online status. """
        return target in self._monitoring

    ## Callbacks.

    async def on_user_online(self, nickname):
        """ Callback called when a monitored user appears online. """
        ...

    async def on_user_offline(self, nickname):
        """ Callback called when a monitored users goes offline. """
        ...

    ## Message handlers.

    async def on_capability_monitor_notify_available(self, value):
        return True

    async def on_raw_730(self, message):
        """ Someone we are monitoring just came online. """
        for target in message.params[1].split(','):
            nickname, metadata = self._parse_user(target)
            await self._sync_user(nickname, metadata)
            await self.on_user_online(nickname)

    async def on_raw_731(self, message):
        """ Someone we are monitoring got offline. """
        for target in message.params[1].split(','):
            nickname, metadata = self._parse_user(target)
            # May be monitoring a user we haven't seen yet
            if nickname in self.users:
                self._destroy_user(nickname, monitor_override=True)
            await self.on_user_offline(nickname)

    async def on_raw_732(self, message):
        """ List of users we're monitoring. """
        for target in message.params[1].split(','):
            nickname, metadata = self._parse_user(target)
            self._monitoring.add(nickname)

    on_raw_733 = isupport.ISUPPORTSupport._ignored  # End of MONITOR list.

    async def on_raw_734(self, message):
        """ Monitor list is full, can't add target. """
        # Remove from monitoring list, not much else we can do.
        to_remove = set()
        for target in message.params[1].split(','):
            nickname, metadata = self._parse_user(target)
            to_remove.add(nickname)
        self._monitoring.difference_update(to_remove)
