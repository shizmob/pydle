import asyncio
import os.path as path
import ssl
import sys

__all__ = ['Connection']

DEFAULT_CA_PATHS = {
    'linux': '/etc/ssl/certs',
    'linux2': '/etc/ssl/certs',
    'freebsd': '/etc/ssl/certs'
}

MESSAGE_THROTTLE_TRESHOLD = 3
MESSAGE_THROTTLE_DELAY = 2


class Connection:
    """ A TCP connection over the IRC protocol. """
    CONNECT_TIMEOUT = 10

    def __init__(self, hostname, port, tls=False, tls_verify=True, tls_certificate_file=None,
                 tls_certificate_keyfile=None, tls_certificate_password=None, ping_timeout=240,
                 source_address=None, eventloop=None):
        self.hostname = hostname
        self.port = port
        self.source_address = source_address
        self.ping_timeout = ping_timeout

        self.tls = tls
        self.tls_context = None
        self.tls_verify = tls_verify
        self.tls_certificate_file = tls_certificate_file
        self.tls_certificate_keyfile = tls_certificate_keyfile
        self.tls_certificate_password = tls_certificate_password

        self.reader = None
        self.writer = None
        self.eventloop = eventloop or asyncio.new_event_loop()

    async def connect(self):
        """ Connect to target. """
        self.tls_context = None

        if self.tls:
            self.tls_context = self.create_tls_context()

        (self.reader, self.writer) = await asyncio.open_connection(
            host=self.hostname,
            port=self.port,
            local_addr=self.source_address,
            ssl=self.tls_context,
            loop=self.eventloop
        )

    def create_tls_context(self):
        """ Transform our regular socket into a TLS socket. """
        # Create context manually, as we're going to set our own options.
        tls_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # Load client/server certificate.
        if self.tls_certificate_file:
            tls_context.load_cert_chain(self.tls_certificate_file, self.tls_certificate_keyfile,
                                        password=self.tls_certificate_password)

        # Set some relevant options:
        # - No server should use SSLv2 or SSLv3 any more, they are outdated and full of security holes. (RFC6176, RFC7568)
        # - Disable compression in order to counter the CRIME attack. (https://en.wikipedia.org/wiki/CRIME_%28security_exploit%29)
        # - Disable session resumption to maintain perfect forward secrecy. (https://timtaubert.de/blog/2014/11/the-sad-state-of-server-side-tls-session-resumption-implementations/)
        for opt in ['NO_SSLv2', 'NO_SSLv3', 'NO_COMPRESSION', 'NO_TICKET']:
            if hasattr(ssl, 'OP_' + opt):
                tls_context.options |= getattr(ssl, 'OP_' + opt)

        # Set TLS verification options.
        if self.tls_verify:
            # Set our custom verification callback, if the library supports it.
            tls_context.set_servername_callback(self.verify_tls)

            # Load certificate verification paths.
            tls_context.set_default_verify_paths()
            if sys.platform in DEFAULT_CA_PATHS and path.isdir(DEFAULT_CA_PATHS[sys.platform]):
                tls_context.load_verify_locations(capath=DEFAULT_CA_PATHS[sys.platform])

            # If we want to verify the TLS connection, we first need a certicate.
            # Check this certificate and its entire chain, if possible, against revocation lists.
            tls_context.verify_mode = ssl.CERT_REQUIRED
            tls_context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN

        return tls_context

    def verify_tls(self, socket, hostname, context):
        """
        Verify a TLS connection. Return behaviour is dependent on the as_callback parameter:
            - If True, a return value of None means verification succeeded, else it failed.
            - If False, a return value of True means verification succeeded, an exception or False means it failed.
        """
        cert = socket.getpeercert()

        try:
            # Make sure the hostnames for which this certificate is valid include the one we're connecting to.
            ssl.match_hostname(cert, hostname)
        except ssl.CertificateError:
            return ssl.ALERT_DESCRIPTION_BAD_CERTIFICATE

        return None

    async def disconnect(self):
        """ Disconnect from target. """
        if not self.connected:
            return

        self.writer.close()
        self.reader = None
        self.writer = None

    @property
    def connected(self):
        """ Whether this connection is... connected to something. """
        return self.reader is not None and self.writer is not None

    def stop(self):
        """ Stop event loop. """
        self.eventloop.call_soon(self.eventloop.stop)

    async def send(self, data):
        """ Add data to send queue. """
        self.writer.write(data)
        await self.writer.drain()

    async def recv(self):
        return await self.reader.readline()
