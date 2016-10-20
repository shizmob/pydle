## sasl.py
# SASL authentication support. Currently we only support PLAIN authentication.
import base64
try:
    import puresasl
    import puresasl.client
except ImportError:
    puresasl = None

from pydle import async
from . import cap

__all__ = [ 'SASLSupport' ]


RESPONSE_LIMIT = 400
EMPTY_MESSAGE = '+'
ABORT_MESSAGE = '*'


class SASLSupport(cap.CapabilityNegotiationSupport):
    """ SASL authentication support. Currently limited to the PLAIN mechanism. """
    SASL_TIMEOUT = 10

    ## Internal overrides.

    def __init__(self, *args, sasl_identity='', sasl_username=None, sasl_password=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sasl_identity = sasl_identity
        self.sasl_username = sasl_username
        self.sasl_password = sasl_password

    def _reset_attributes(self):
        super()._reset_attributes()
        self._sasl_client = None
        self._sasl_timer = None
        self._sasl_challenge = b''
        self._sasl_mechanisms = None


    ## SASL functionality.

    @async.coroutine
    def _sasl_start(self):
        """ Initiate SASL authentication. """
        # The rest will be handled in on_raw_authenticate()/_sasl_respond().
        yield from self.rawmsg('AUTHENTICATE', self._sasl_client.mechanism.upper())
        self._sasl_timer = self.eventloop.schedule_async_in(self.SASL_TIMEOUT, self._sasl_abort(timeout=True))

    @async.coroutine
    def _sasl_abort(self, timeout=False):
        """ Abort SASL authentication. """
        if timeout:
            self.logger.error('SASL authentication timed out: aborting.')
        else:
            self.logger.error('SASL authentication aborted.')

        # We're done here.
        yield from self.rawmsg('AUTHENTICATE', ABORT_MESSAGE)
        yield from self._capability_negotiated('sasl')

    @async.coroutine
    def _sasl_end(self):
        """ Finalize SASL authentication. """
        yield from self._capability_negotiated('sasl')

    @async.coroutine
    def _sasl_respond(self):
        """ Respond to SASL challenge with response. """
        # Formulate a response.
        try:
            response = self._sasl_client.process(self._sasl_challenge)
        except puresasl.SASLError:
            response = None

        if response is None:
            self.logger.warning('SASL challenge processing failed: aborting SASL authentication.')
            yield from self._sasl_abort()

        response = base64.b64encode(response).decode(self.encoding)
        to_send = len(response)
        self._sasl_challenge = b''

        # Send response in chunks.
        while to_send > 0:
            yield from self.rawmsg('AUTHENTICATE', response[:RESPONSE_LIMIT])
            response = response[RESPONSE_LIMIT:]
            to_send -= RESPONSE_LIMIT

        # If our message fit exactly in SASL_RESPOSE_LIMIT-byte chunks, send an empty message to indicate we're done.
        if to_send == 0:
            yield from self.rawmsg('AUTHENTICATE', EMPTY_MESSAGE)


    ## Capability callbacks.

    @async.coroutine
    def on_capability_sasl_available(self, value):
        """ Check whether or not SASL is available. """
        if value:
            self._sasl_mechanisms = value.upper().split(',')
        else:
            self._sasl_mechanisms = ['PLAIN']

        if self.sasl_username and self.sasl_password:
            if puresasl:
                return True
            self.logger.warning('SASL credentials set but puresasl module not found: not initiating SASL authentication.')
        return False

    @async.coroutine
    def on_capability_sasl_enabled(self):
        """ Start SASL authentication. """
        self._sasl_client = puresasl.client.SASLClient(self.connection.hostname, 'irc',
            username=self.sasl_username,
            password=self.sasl_password,
            identity=self.sasl_identity
        )
        try:
            self._sasl_client.choose_mechanism(self._sasl_mechanisms, allow_anonymous=False)
        except puresasl.SASLError:
            self.logger.exception('SASL mechanism choice failed: aborting SASL authentication.')
            return cap.FAILED

        # Initialize SASL.
        yield from self._sasl_start()
        # Tell caller we need more time, and to not end capability negotiation just yet.
        return cap.NEGOTIATING


    ## Message handlers.

    @async.coroutine
    def on_raw_authenticate(self, message):
        """ Received part of the authentication challenge. """
        # Cancel timeout timer.
        self.eventloop.unschedule(self._sasl_timer)

        # Add response data.
        response = ' '.join(message.params)
        if response != EMPTY_MESSAGE:
            self._sasl_challenge += base64.b64decode(response)

        # If the response ain't exactly SASL_RESPONSE_LIMIT bytes long, it's the end. Process.
        if len(response) % RESPONSE_LIMIT > 0:
            yield from self._sasl_respond()
        else:
            # Response not done yet. Restart timer.
            self._sasl_timer = self.eventloop.schedule_async_in(self.SASL_TIMEOUT, self._sasl_abort(timeout=True))


    on_raw_900 = cap.CapabilityNegotiationSupport._ignored # You are now logged in as...

    @async.coroutine
    def on_raw_903(self, message):
        """ SASL authentication successful. """
        yield from self._sasl_end()

    @async.coroutine
    def on_raw_904(self, message):
        """ Invalid mechanism or authentication failed. Abort SASL. """
        yield from self._sasl_abort()

    @async.coroutine
    def on_raw_905(self, message):
        """ Authentication failed. Abort SASL. """
        yield from self._sasl_abort()

    on_raw_906 = cap.CapabilityNegotiationSupport._ignored # Completed registration while authenticating/registration aborted.
    on_raw_907 = cap.CapabilityNegotiationSupport._ignored # Already authenticated over SASL.
