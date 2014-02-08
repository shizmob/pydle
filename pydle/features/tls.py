## tls.py
# TLS support.
import ssl
import pydle.protocol
from pydle.features import rfc1459
from .. import connection

__all__ = [ 'TLSSupport' ]

DEFAULT_TLS_PORT = 6697


class TLSSupport(rfc1459.RFC1459Support):
    """ TLS and STARTTLS support. """

    ## Internal overrides.

    def __init__(self, *args, tls_client_cert=None, tls_client_cert_key=None, tls_client_cert_password=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tls_client_cert = tls_client_cert
        self.tls_client_cert_key = tls_client_cert_key
        self.tls_client_cert_password = tls_client_cert_password

    def _connect(self, hostname, port=None, reconnect=False, password=None, encoding=pydle.protocol.DEFAULT_ENCODING, channels=[], tls=False, tls_verify=False, source_address=None):
        """ Connect to IRC server, optionally over TLS. """
        self.password = password
        if not reconnect:
            self._autojoin_channels = channels

        if not port:
            if tls:
                port = DEFAULT_TLS_PORT
            else:
                port = pydle.protocol.DEFAULT_PORT

        # Create connection if we can't reuse it.
        if not reconnect:
            self.connection = connection.Connection(hostname, port,
                tls=tls, tls_verify=tls_verify,
                tls_certificate_file=self.tls_client_cert,
                tls_certificate_keyfile=self.tls_client_cert_key,
                tls_certificate_password=self.tls_client_cert_password,
                encoding=encoding, source_address=source_address)

        # Connect.
        self.connection.connect()

    def _register(self):   
        # Send STARTTLS if we're not on TLS already.
        if self.registered:
            return
        if not self.connection.tls:
            self.rawmsg('STARTTLS')
        super()._register()


    ## Message callbacks.

    def on_raw_421(self, message):
        """ Hijack to ignore absence of STARTTLS support. """
        if message.params[0] == 'STARTTLS':
            return
        super().on_raw_421(message)

    def on_raw_451(self, mesage):
        """ Hijack to ignore absence of STARTTLS support. """
        if message.params[0] == 'STARTTLS':
            return
        super().on_raw_451(message)

    def on_raw_670(self, message):
        """ Got the OK from the server to start a TLS connection. Let's roll. """
        self.connection.tls = True
        self.connection.setup_tls()

    def on_raw_691(self, message):
        """ Error setting up TLS server-side. """
        self.logger.err('Server experienced error in setting up TLS, not proceeding with TLS setup: {}', message.params[0])
