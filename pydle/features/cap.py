## cap.py
# Server <-> client optional extension indication support.
# See also: http://ircv3.atheme.org/specification/capability-negotiation-3.1
import re
from .. import client

__all__ = [ 'CapabilityNegotiationSupport', 'NEGOTIATED', 'NEGOTIATING', 'FAILED' ]


DISABLED_PREFIX = '-'
ACKNOWLEDGEMENT_REQUIRED_PREFIX = '~'
STICKY_PREFIX = '='
PREFIXES = '-~='
NEGOTIATING = True
NEGOTIATED = None
FAILED = False


class CapabilityNegotiationSupport(client.BasicClient):
    """ CAP command support. """

    ## Internal overrides.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._capabilities = {}
        self._capabilities_requested = set()
        self._capabilities_negotiating = set()

    def _register(self):
        """ Hijack registration to send a CAP LS first. """
        if self.registered:
           return

        # Ask server to list capabilities.
        self.rawmsg('CAP', 'LS')

        # Register as usual.
        super()._register()

    def _capability_normalize(self, cap):
        return cap.lstrip(PREFIXES).lower()


    ## API.

    def capability_negotiated(self, capab):
        """ Mark capability as negotiated, and end negotiation if we're done. """
        self._capabilities_negotiating.discard(capab)

        if not self._capabilities_requested and not self._capabilities_negotiating:
            self.rawmsg('CAP', 'END')


    ## Message handlers.

    def on_raw_cap(self, source, params):
        """ Handle CAP message. """
        target, subcommand, params = params[0], params[1], params[2:]

        # Call handler.
        attr = 'on_raw_cap_' + subcommand.lower()
        if hasattr(self, attr):
            getattr(self, attr)(params)
        else:
            self.logger.warning('Unknown CAP subcommand sent from server: {}', subcommand)

    def on_raw_cap_ls(self, params):
        """ Update capability mapping. Request capabilities. """
        to_request = set()

        for capab in params[0].split():
            cp = self._capability_normalize(capab)

            # Only process new capabilities.
            if cp in self._capabilities:
                continue

            # Check if we support the capability.
            attr = 'on_capability_' + capability_to_identifier(cp) + '_available'
            supported = getattr(self, attr)() if hasattr(self, attr) else False

            if supported:
                to_request.add(cp)
            else:
                self._capabilities[cp] = False

        if to_request:
            # Request some capabilities.
            self._capabilities_requested.union(to_request)
            self.rawmsg('CAP', 'REQ', ' '.join(to_request))
        else:
            # No capabilities requested, end negotiation.
            self.rawmsg('CAP', 'END')

    def on_raw_cap_list(self, params):
        """ Update active capabilities. """
        self._capabilities = { capab: False for capab in self._capabilities }

        for capab in params[0].split():
            capab = self._capability_normalize(capab)
            self._capabilities[capab] = True

    def on_raw_cap_ack(self, params):
        """ Update active capabilities: requested capability accepted. """
        for capab in params[0].split():
            cp = self._capability_normalize(capab)
            self._capabilities_requested.discard(cp)

            # Determine capability type and callback.
            if capab.startswith(DISABLED_PREFIX):
                self._capabilities[cp] = False
                attr = 'on_capability_' + capability_to_identifier(cp) + '_disabled'
            elif capab.startswith(STICKY_PREFIX):
                # Can't disable it. Do nothing.
                self.logger.err('Could not disable capability {}.', cp)
                continue
            else:
                self._capabilities[cp] = True
                attr = 'on_capability_' + capability_to_identifier(cp) + '_enabled'

            # Indicate we're gonna use this capability if needed.
            if capab.startswith(ACKNOWLEDGEMENT_REQUIRED_PREFIX):
                self.rawmsg('CAP', 'ACK', cp)

            # Run callback.
            if hasattr(self, attr):
                status = getattr(self, attr)()
            else:
                status = NEGOTIATED

            # If the process needs more time, add it to the database and end later.
            if status == NEGOTIATING:
                self._capabilities_negotiating.add(cp)
            elif status == FAILED:
                # Ruh-roh, negotiation failed. Disable the capability.
                self.logger.warn('Capability negotiation for {} failed. Attempting to disable capability again.', cp)

                self.rawmsg('CAP', 'REQ', '-' + cp)
                self._capabilities_requested.add(cp)

        # If we have no capabilities left to process, end it.
        if not self._capabilities_requested and not self._capabilities_negotiating:
            self.rawmsg('CAP', 'END')

    def on_raw_cap_nak(self, params):
        """ Update active capabilities: requested capability rejected. """
        for capab in params[0].split():
            capab = self._capability_normalize(capab)
            self._capabilities[capab] = False
            self._capabilities_requested.discard(capab)

        # If we have no capabilities left to process, end it.
        if not self._capabilities_requested and not self._capabilities_negoatiating:
            self.rawmsg('CAP', 'END')


    def on_raw_410(self, source, params):
        """ Unknown CAP subcommand or CAP error. Force-end negotiations. """
        self.logger.err('Server sent "Unknown CAP subcommand: {}". Aborting capability negotiation.', params[0])

        self._capabilities_requested = set()
        self._capabilities_negotiating = set()
        self.rawmsg('CAP', 'END')

    def on_raw_421(self, source, params):
        """ Hijack to ignore the absence of a CAP command. """
        if params[0] == 'CAP':
            return
        super().on_raw_421(source, params)

    def on_raw_451(self, source, params):
        """ Hijack to ignore the absence of a CAP command. """
        if params[0] == 'CAP':
            return
        super().on_raw_451(source, params)


## Helpers.

def capability_to_identifier(name):
    """ Clean up capability so it works for a Python identifier. """
    name = name.lower()
    name = re.sub('[^a-z]', '_', name)
    return name
