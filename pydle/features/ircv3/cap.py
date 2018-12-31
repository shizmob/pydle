## cap.py
# Server <-> client optional extension indication support.
# See also: http://ircv3.atheme.org/specification/capability-negotiation-3.1
import pydle.protocol
from pydle.features import rfc1459

__all__ = [ 'CapabilityNegotiationSupport', 'NEGOTIATED', 'NEGOTIATING', 'FAILED' ]


DISABLED_PREFIX = '-'
ACKNOWLEDGEMENT_REQUIRED_PREFIX = '~'
STICKY_PREFIX = '='
PREFIXES = '-~='
CAPABILITY_VALUE_DIVIDER = '='
NEGOTIATING = True
NEGOTIATED = None
FAILED = False


class CapabilityNegotiationSupport(rfc1459.RFC1459Support):
    """ CAP command support. """

    ## Internal overrides.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._capabilities = {}
        self._capabilities_requested = set()
        self._capabilities_negotiating = set()

    async def _register(self):
        """ Hijack registration to send a CAP LS first. """
        if self.registered:
            self.logger.debug("skipping cap registration, already registered!")
            return

        # Ask server to list capabilities.
        await self.rawmsg('CAP', 'LS', '302')

        # Register as usual.
        await super()._register()

    def _capability_normalize(self, cap):
        cap = cap.lstrip(PREFIXES).lower()
        if CAPABILITY_VALUE_DIVIDER in cap:
            cap, _, value = cap.partition(CAPABILITY_VALUE_DIVIDER)
        else:
            value = None

        return cap, value


    ## API.

    async def _capability_negotiated(self, capab):
        """ Mark capability as negotiated, and end negotiation if we're done. """
        self._capabilities_negotiating.discard(capab)

        if not self._capabilities_requested and not self._capabilities_negotiating:
            await self.rawmsg('CAP', 'END')


    ## Message handlers.

    async def on_raw_cap(self, message):
        """ Handle CAP message. """
        target, subcommand = message.params[:2]
        params = message.params[2:]

        # Call handler.
        attr = 'on_raw_cap_' + pydle.protocol.identifierify(subcommand)
        if hasattr(self, attr):
            await getattr(self, attr)(params)
        else:
            self.logger.warning('Unknown CAP subcommand sent from server: %s', subcommand)

    async def on_raw_cap_ls(self, params):
        """ Update capability mapping. Request capabilities. """
        to_request = set()

        for capab in params[0].split():
            capab, value = self._capability_normalize(capab)

            # Only process new capabilities.
            if capab in self._capabilities:
                continue

            # Check if we support the capability.
            attr = 'on_capability_' + pydle.protocol.identifierify(capab) + '_available'
            supported = (await getattr(self, attr)(value)) if hasattr(self, attr) else False

            if supported:
                if isinstance(supported, str):
                    to_request.add(capab + CAPABILITY_VALUE_DIVIDER + supported)
                else:
                    to_request.add(capab)
            else:
                self._capabilities[capab] = False

        if to_request:
            # Request some capabilities.
            self._capabilities_requested.update(x.split(CAPABILITY_VALUE_DIVIDER, 1)[0] for x in to_request)
            await self.rawmsg('CAP', 'REQ', ' '.join(to_request))
        else:
            # No capabilities requested, end negotiation.
            await self.rawmsg('CAP', 'END')

    async def on_raw_cap_list(self, params):
        """ Update active capabilities. """
        self._capabilities = { capab: False for capab in self._capabilities }

        for capab in params[0].split():
            capab, value = self._capability_normalize(capab)
            self._capabilities[capab] = value if value else True

    async def on_raw_cap_ack(self, params):
        """ Update active capabilities: requested capability accepted. """
        for capab in params[0].split():
            cp, value = self._capability_normalize(capab)
            self._capabilities_requested.discard(cp)

            # Determine capability type and callback.
            if capab.startswith(DISABLED_PREFIX):
                self._capabilities[cp] = False
                attr = 'on_capability_' + pydle.protocol.identifierify(cp) + '_disabled'
            elif capab.startswith(STICKY_PREFIX):
                # Can't disable it. Do nothing.
                self.logger.error('Could not disable capability %s.', cp)
                continue
            else:
                self._capabilities[cp] = value if value else True
                attr = 'on_capability_' + pydle.protocol.identifierify(cp) + '_enabled'

            # Indicate we're gonna use this capability if needed.
            if capab.startswith(ACKNOWLEDGEMENT_REQUIRED_PREFIX):
                await self.rawmsg('CAP', 'ACK', cp)

            # Run callback.
            if hasattr(self, attr):
                status = await getattr(self, attr)()
            else:
                status = NEGOTIATED

            # If the process needs more time, add it to the database and end later.
            if status == NEGOTIATING:
                self._capabilities_negotiating.add(cp)
            elif status == FAILED:
                # Ruh-roh, negotiation failed. Disable the capability.
                self.logger.warning('Capability negotiation for %s failed. Attempting to disable capability again.', cp)

                await self.rawmsg('CAP', 'REQ', '-' + cp)
                self._capabilities_requested.add(cp)

        # If we have no capabilities left to process, end it.
        if not self._capabilities_requested and not self._capabilities_negotiating:
            await self.rawmsg('CAP', 'END')

    async def on_raw_cap_nak(self, params):
        """ Update active capabilities: requested capability rejected. """
        for capab in params[0].split():
            capab, _ = self._capability_normalize(capab)
            self._capabilities[capab] = False
            self._capabilities_requested.discard(capab)

        # If we have no capabilities left to process, end it.
        if not self._capabilities_requested and not self._capabilities_negotiating:
            await self.rawmsg('CAP', 'END')

    async def on_raw_cap_del(self, params):
        for capab in params[0].split():
            attr = 'on_capability_{}_disabled'.format(pydle.protocol.identifierify(capab))
            if self._capabilities.get(capab, False) and hasattr(self, attr):
                await getattr(self, attr)()
        await self.on_raw_cap_nak(params)

    async def on_raw_cap_new(self, params):
        await self.on_raw_cap_ls(params)

    async def on_raw_410(self, message):
        """ Unknown CAP subcommand or CAP error. Force-end negotiations. """
        self.logger.error('Server sent "Unknown CAP subcommand: %s". Aborting capability negotiation.', message.params[0])

        self._capabilities_requested = set()
        self._capabilities_negotiating = set()
        await self.rawmsg('CAP', 'END')

    async def on_raw_421(self, message):
        """ Hijack to ignore the absence of a CAP command. """
        if message.params[0] == 'CAP':
            return
        await super().on_raw_421(message)

    async def on_raw_451(self, message):
        """ Hijack to ignore the absence of a CAP command. """
        if message.params[0] == 'CAP':
            return
        await super().on_raw_451(message)
