## sasl.py
# SASL authentication support. Currently we only support PLAIN authentication.
import threading
import base64
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

    def __init__(self, *args, sasl_identity='', sasl_username=None, sasl_password=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sasl_identity = sasl_identity
        self.sasl_username = sasl_username
        self.sasl_password = sasl_password

    def _reset_attributes(self):
        super()._reset_attributes()
        self._sasl_aborted = False
        self._sasl_challenge = b''
        self._sasl_timer = None


    ## SASL functionality.

    def _sasl_start(self):
        """ Initiate SASL authentication. """
        # The rest will be handled in on_raw_authenticate()/_sasl_respond().
        self.rawmsg('AUTHENTICATE', 'PLAIN')

    def _sasl_abort(self, timeout=False):
        """ Abort SASL authentication. """
        # You Only Abort Once
        if not self._sasl_aborted:
            if timeout:
                self.logger.err('SASL authentication timed out: aborting.')
            else:
                self.logger.err('SASL authentication aborted.')
            self._sasl_aborted = True

            # We're done here.
            self.rawmsg('AUTHENTICATE', ABORT_MESSAGE)
            self.capability_negotiated('sasl')

    def _sasl_end(self):
        """ Finalize SASL authentication. """
        self.capability_negotiated('sasl')

    def _sasl_respond(self):
        """ Respond to SASL challenge with response. """
        # Formulate a response.
        saslclient = puresasl.client.SASLClient(self.connection.hostname, 'irc', mechanism='PLAIN',
            username=self.sasl_username, password=self.sasl_password, identity=self.sasl_identity)

        response = base64.b64encode(saslclient.process(challenge=self._sasl_challenge)).decode(self.connection.encoding)
        to_send = len(response)

        # Send response in chunks.
        while to_send > 0:
            self.rawmsg('AUTHENTICATE', response[:RESPONSE_LIMIT])
            response = response[RESPONSE_LIMIT:]
            to_send -= RESPONSE_LIMIT

        # If our message fit exactly in SASL_RESPOSE_LIMIT-byte chunks, send an empty message to indicate we're done.
        if to_send == 0:
            self.rawmsg('AUTHENTICATE', EMPTY_MESSAGE)


    ## Capability callbacks.

    def on_capability_sasl_available(self):
        """ Check whether or not SASL is available. """
        if self.sasl_username and self.sasl_password:
            if puresasl:
                return True
            self.logger.warn('SASL credentials set but puresasl module not found: not initiating SASL authentication.')
        return False

    def on_capability_sasl_enabled(self):
        """ Start SASL authentication. """
        # Set a timeout handler.
        self._sasl_timer = threading.Timer(self.SASL_TIMEOUT, self._sasl_abort)
        self._sasl_timer.start()

        # Initialize SASL.
        self._sasl_start()

        # Tell caller we need more time, and to not end capability negotiation just yet.
        return cap.NEGOTIATING


    ## Message handlers.

    def on_raw_authenticate(self, source, params):
        """ Received part of the authentication challenge. """
        # Cancel timeout timer.
        self._sasl_timer.cancel()

        # Add response data.
        response = ' '.join(params)
        if response != EMPTY_MESSAGE:
            self._sasl_challenge += base64.b64decode(response)

        # If the response ain't exactly SASL_RESPONSE_LIMIT bytes long, it's the end. Process.
        if len(response) % RESPONSE_LIMIT > 0:
            self._sasl_respond()
        else:
            # Response not done yet. Restart timer.
            self._sasl_timer = threading.Timer(self.SASL_TIMEOUT, self._sasl_abort)
            self._sasl_timer.start()


    on_raw_900 = cap.CapabilityNegotiationSupport._ignored # You are now logged in as...

    def on_raw_903(self, source, params):
        """ SASL authentication successful. """
        self._sasl_end()

    def on_raw_904(self, source, params):
        """ Invalid mechanism or authentication failed. Abort SASL. """
        self._sasl_abort()

    def on_raw_905(self, source_params):
        """ Authentication failed. Abort SASL. """
        self._sasl_abort()

    on_raw_906 = cap.CapabilityNegotiationSupport._ignored # Completed registration while authenticating/registration aborted.
    on_raw_907 = cap.CapabilityNegotiationSupport._ignored # Already authenticated over SASL.
