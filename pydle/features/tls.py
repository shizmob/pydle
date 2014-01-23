## tls.py
# TLS support.
import ssl

from .. import client
from .. import connection
from .. import protocol

__all__ = [ 'TLSSupport' ]


class TLSSupport(client.BasicClient):
    """ TLS and STARTTLS support. """

    ## Internal overrides.

    def __init__(self, *args, tls_client_cert=None, tls_client_cert_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tls_client_cert = tls_client_cert
        self.tls_client_cert_key = tls_client_cert_key

    def connect(self, hostname=None, port=None, password=None, encoding='utf-8', channels=[], tls=False, tls_verify=False):
        """ Connect to IRC server, optionally over TLS. """
        # Disconnect from current connection.
        if self.connected:
            self.disconnect()

        self.password = password
        self._autojoin_channels = channels

        if not port:
            if tls:
                port = protocol.DEFAULT_TLS_PORT
            else:
                port = protocol.DEFAULT_PORT

        # Create connection.
        self.connection = connection.Connection(hostname, port,
            tls=tls, tls_verify=tls_verify,
            tls_certificate_file=self.tls_client_cert,
            tls_certificate_keyfile=self.tls_client_cert_key,
            encoding=encoding)

        # Connect.
        self.connection.connect()

        # Set logger name.
        self.logger.name = self.__class__.__name__ + ':' + self.server_tag

        # Send STARTTLS if we're not on TLS already.
        if not tls:
            self.rawmsg('STARTTLS')

        # And initiate the IRC connection.
        self._register()


    ## Message callbacks.

    def on_raw_421(self, source, params):
        """ Hijack to ignore absence of STARTTLS support. """
        if params[0] == 'STARTTLS':
            return
        super().on_raw_421(source, params)

    def on_raw_451(self, source, params):
        """ Hijack to ignore absence of STARTTLS support. """
        if params[0] == 'STARTTLS':
            return
        super().on_raw_451(source, params)

    def on_raw_670(self, source, params):
        """ Got the OK from the server to start a TLS connection. Let's roll. """
        self.connection.tls = True
        self.connection.setup_tls()

    def on_raw_691(self, source, params):
        """ Error setting up TLS server-side. """
        self.logger.err('Server experienced error in setting up TLS, not proceeding with TLS setup: {}', params[0])
