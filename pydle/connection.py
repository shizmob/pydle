import sys
import os
import os.path as path
import collections
import time
import threading
import datetime

import socket
import ssl
import errno

from . import async
from . import protocol

__all__ = [ 'BUFFER_SIZE', 'Connection' ]


DEFAULT_CA_PATHS = {
    'linux': '/etc/ssl/certs',
    'linux2': '/etc/ssl/certs',
    'freebsd': '/etc/ssl/certs'
}
if hasattr(ssl, 'SSLWantReadError') and hasattr(ssl, 'SSLWantWriteError'):
    WOULD_BLOCK_ERRORS = (ssl.SSLWantReadError, ssl.SSLWantWriteError)
else:
    WOULD_BLOCK_ERRORS = ()
WOULD_BLOCK_ERRNOS = [
    getattr(errno, 'EAGAIN', None),
    getattr(errno, 'EWOULDBLOCK', None),
]

BUFFER_SIZE = 4096
MESSAGE_THROTTLE_TRESHOLD = 3
MESSAGE_THROTTLE_DELAY = 2


class Connection:
    """ A TCP connection over the IRC protocol. """
    CONNECT_TIMEOUT = 10

    def __init__(self, hostname, port, tls=False, tls_verify=True, tls_certificate_file=None, tls_certificate_keyfile=None, tls_certificate_password=None, ping_timeout=240, source_address=None, eventloop=None):
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
        self.eventloop = eventloop or async.EventLoop()

    @async.coroutine
    def connect(self):
        """ Connect to target. """
        self.tls_context = None

        if self.tls:
            self.tls_context = self.create_tls_context()
        (self.reader, self.writer) = yield from self.eventloop.connect((self.hostname, self.port), local_addr=self.source_address, tls=self.tls_context)
        if self.tls:
            self.setup_tls(self.writer.transport, self.tls_context)

    def create_tls_context(self):
        """ Transform our regular socket into a TLS socket. """
        # Create context manually, as we're going to set our own options.
        tls_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # Load client/server certificate.
        if self.tls_certificate_file:
            tls_context.load_cert_chain(self.tls_certificate_file, self.tls_certificate_keyfile, password=self.tls_certificate_password)

        # Set some relevant options:
        # - No server should use SSLv2 any more, it's outdated and full of security holes.
        # - Disable compression in order to counter the CRIME attack. (https://en.wikipedia.org/wiki/CRIME_%28security_exploit%29)
        for opt in [ 'NO_SSLv2', 'NO_COMPRESSION']:
            if hasattr(ssl, 'OP_' + opt):
                tls_context.options |= getattr(ssl, 'OP_' + opt)

        # Set TLS verification options.
        if self.tls_verify:
            # Set our custom verification callback, if the library supports it.
            if hasattr(tls_context, 'set_servername_callback'):
                tls_context.set_servername_callback(self.verify_tls)

            # Load certificate verification paths.
            tls_context.set_default_verify_paths()
            if sys.platform in DEFAULT_CA_PATHS and path.isdir(DEFAULT_CA_PATHS[sys.platform]):
                tls_context.load_verify_locations(capath=DEFAULT_CA_PATHS[sys.platform])

            # If we want to verify the TLS connection, we first need a certicate.
            # Check this certificate and its entire chain, if possible, against revocation lists.
            tls_context.verify_mode = ssl.CERT_REQUIRED
            if hasattr(tls_context, 'verify_flags'):
                tls_context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN

        return tls_context

    def setup_tls(self, transport, context):
        if not hasattr(context, 'set_servername_callback'):
            self.verify_tls(transport.get_extra_info('ssl_object'), self.hostname, context, as_callback=False)

    def verify_tls(self, socket, hostname, context, as_callback=True):
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
            if not as_callback:
                raise

            # Try to give back a more elaborate error message if possible.
            if hasattr(ssl, 'ALERT_DESCRIPTION_BAD_CERTIFICATE'):
                return ssl.ALERT_DESCRIPTION_BAD_CERTIFICATE
            return True

        # Verification done.
        if as_callback:
            return None
        return True

    @async.coroutine
    def disconnect(self):
        """ Disconnect from target. """
        if not self.connected:
            return

        self.writer.close()

        with self.send_queue_lock:
            self.send_queue = None
            self.unthrottled_sends = 0
            self.last_sent = None

    @property
    def connected(self):
        """ Whether this connection is... connected to something. """
        return self.reader is not None and self.writer is not None


    def stop(self):
        """ Stop event loop. """
        self.eventloop.schedule(lambda: self.eventloop.stop())


    @async.coroutine
    def send(self, data):
        """ Add data to send queue. """
        self.writer.write(data)
        yield from self.writer.drain()

    @async.coroutine
    def recv(self):
        return (yield from self.reader.readline())
