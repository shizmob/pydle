## sasl.py
# SASL authentication support. Currently we only support PLAIN authentication.
import base64
from functools import partial

try:
    import puresasl
    import puresasl.client
except ImportError:
    puresasl = None

from . import cap

__all__ = [ 'SASLSupport' ]


RESPONSE_LIMIT = 400
EMPTY_MESSAGE = '+'
ABORT_MESSAGE = '*'


class SASLSupport(cap.CapabilityNegotiationSupport):
    """ SASL authentication support. Currently limited to the PLAIN mechanism. """
    SASL_TIMEOUT = 10

    ## Internal overrides.

    def __init__(self, *args, sasl_identity='', sasl_username=None, sasl_password=None, sasl_mechanism=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sasl_identity = sasl_identity
        self.sasl_username = sasl_username
        self.sasl_password = sasl_password
        self.sasl_mechanism = sasl_mechanism

    def _reset_attributes(self):
        super()._reset_attributes()
        self._sasl_client = None
        self._sasl_timer = None
        self._sasl_challenge = b''
        self._sasl_mechanisms = None


    ## SASL functionality.

    async def _sasl_start(self, mechanism):
        """ Initiate SASL authentication. """
        # The rest will be handled in on_raw_authenticate()/_sasl_respond().
        await self.rawmsg('AUTHENTICATE', mechanism)
        # create a partial, required for our callback to get the kwarg
        _sasl_partial = partial(self._sasl_abort, timeout=True)
        self._sasl_timer = self.eventloop.call_later(self.SASL_TIMEOUT, _sasl_partial)

    async def _sasl_abort(self, timeout=False):
        """ Abort SASL authentication. """
        if timeout:
            self.logger.error('SASL authentication timed out: aborting.')
        else:
            self.logger.error('SASL authentication aborted.')

        if self._sasl_timer:
            self._sasl_timer.cancel()

            self._sasl_timer = None

        # We're done here.
        await self.rawmsg('AUTHENTICATE', ABORT_MESSAGE)
        await self._capability_negotiated('sasl')

    async def _sasl_end(self):
        """ Finalize SASL authentication. """
        if self._sasl_timer:
            self._sasl_timer.cancel()
            self._sasl_timer = None
        await self._capability_negotiated('sasl')

    async def _sasl_respond(self):
        """ Respond to SASL challenge with response. """
        # Formulate a response.
        if self._sasl_client:
            try:
                response = self._sasl_client.process(self._sasl_challenge)
            except puresasl.SASLError:
                response = None

            if response is None:
                self.logger.warning('SASL challenge processing failed: aborting SASL authentication.')
                await self._sasl_abort()
        else:
            response = b''

        response = base64.b64encode(response).decode(self.encoding)
        to_send = len(response)
        self._sasl_challenge = b''

        # Send response in chunks.
        while to_send > 0:
            await self.rawmsg('AUTHENTICATE', response[:RESPONSE_LIMIT])
            response = response[RESPONSE_LIMIT:]
            to_send -= RESPONSE_LIMIT

        # If our message fit exactly in SASL_RESPOSE_LIMIT-byte chunks, send an empty message to indicate we're done.
        if to_send == 0:
            await self.rawmsg('AUTHENTICATE', EMPTY_MESSAGE)


    ## Capability callbacks.

    async def on_capability_sasl_available(self, value):
        """ Check whether or not SASL is available. """
        if value:
            self._sasl_mechanisms = value.upper().split(',')
        else:
            self._sasl_mechanisms = None

        if self.sasl_mechanism == 'EXTERNAL' or (self.sasl_username and self.sasl_password):
            if self.sasl_mechanism == 'EXTERNAL' or puresasl:
                return True
            self.logger.warning('SASL credentials set but puresasl module not found: not initiating SASL authentication.')
        return False

    async def on_capability_sasl_enabled(self):
        """ Start SASL authentication. """
        if self.sasl_mechanism:
            if self._sasl_mechanisms and self.sasl_mechanism not in self._sasl_mechanisms:
                self.logger.warning('Requested SASL mechanism is not in server mechanism list: aborting SASL authentication.')
                return cap.failed
            mechanisms = [self.sasl_mechanism]
        else:
            mechanisms = self._sasl_mechanisms or ['PLAIN']

        if mechanisms == ['EXTERNAL']:
            mechanism = 'EXTERNAL'
        else:
            self._sasl_client = puresasl.client.SASLClient(self.connection.hostname, 'irc',
                username=self.sasl_username,
                password=self.sasl_password,
                identity=self.sasl_identity
            )

            try:
                self._sasl_client.choose_mechanism(mechanisms, allow_anonymous=False)
            except puresasl.SASLError:
                self.logger.exception('SASL mechanism choice failed: aborting SASL authentication.')
                return cap.FAILED
            mechanism = self._sasl_client.mechanism.upper()

        # Initialize SASL.
        await self._sasl_start(mechanism)
        # Tell caller we need more time, and to not end capability negotiation just yet.
        return cap.NEGOTIATING


    ## Message handlers.

    async def on_raw_authenticate(self, message):
        """ Received part of the authentication challenge. """
        # Cancel timeout timer.
        if self._sasl_timer:
            self._sasl_timer.cancel()
            self._sasl_timer = None

        # Add response data.
        response = ' '.join(message.params)
        if response != EMPTY_MESSAGE:
            self._sasl_challenge += base64.b64decode(response)

        # If the response ain't exactly SASL_RESPONSE_LIMIT bytes long, it's the end. Process.
        if len(response) % RESPONSE_LIMIT > 0:
            await self._sasl_respond()
        else:
            # Response not done yet. Restart timer.
            self._sasl_timer = self.eventloop.call_later(self.SASL_TIMEOUT, self._sasl_abort(timeout=True))


    on_raw_900 = cap.CapabilityNegotiationSupport._ignored # You are now logged in as...

    async def on_raw_903(self, message):
        """ SASL authentication successful. """
        await self._sasl_end()

    async def on_raw_904(self, message):
        """ Invalid mechanism or authentication failed. Abort SASL. """
        await self._sasl_abort()

    async def on_raw_905(self, message):
        """ Authentication failed. Abort SASL. """
        await self._sasl_abort()

    on_raw_906 = cap.CapabilityNegotiationSupport._ignored # Completed registration while authenticating/registration aborted.
    on_raw_907 = cap.CapabilityNegotiationSupport._ignored # Already authenticated over SASL.
