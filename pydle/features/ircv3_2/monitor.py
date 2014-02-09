## monitor.py
# Online status monitoring support.
from pydle.features.ircv3_1 import cap


class MonitoringSupport(cap.CapabilityNegotiationSupport):
    """ Support for monitoring the online/offline status of certain targets. """

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._monitoring = set()

    def _destroy_user(self, nickname, channel=None, monitor_override=False):
        # Override _destroy_user to not remove user if they are being monitored by us.
        if channel:
            channels = [ self.channels[channel] ]
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

    def monitor(self, target):
        if 'monitor-notify' in self._capabilities and not self.is_monitoring(target):
            self.rawmsg('MONITOR', '+', target)
            self._monitoring.add(target)

    def unmonitor(self, target):
        if 'monitor-notify' in self._capabilities and self.is_monitoring(target):
            self.rawmsg('MONITOR', '-', target)
            self._monitoring.remove(target)

    def is_monitoring(self, target):
        return target in self._monitoring


    ## Callbacks.

    def on_capability_monitor_notify_available(self):
        return True

    def on_raw_730(self, message):
        """ Someone we are monitoring just came online. """
        for nick in message.params[1].split(','):
            self._create_user(nick)

    def on_raw_731(self, message):
        """ Someone we are monitoring got offline. """
        for nick in message.params[1].split(','):
            self._destroy_user(nick, monitor_override=True)

    def on_raw_732(self, message):
        """ List of users we're monitoring. """
        self._monitoring.update(message.params[1].split(','))

    on_raw_733 = cap.CapabilityNegotiationSupport._ignored  # End of MONITOR list.

    def on_raw_734(self, message):
        """ Monitor list is full, can't add target. """
        # Remove from monitoring list, not much else we can do.
        self._monitoring.difference_update(message.params[1].split(','))
