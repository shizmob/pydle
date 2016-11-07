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

        self.socket = None
        self.socket_lock = threading.RLock()
        self.eventloop = eventloop or async.EventLoop()
        self.handlers = { 'read': [], 'write': [], 'error': [] }

        self.send_queue = collections.deque()
        self.send_queue_lock = threading.RLock()
        self.unthrottled_sends = 0
        self.throttle = True
        self.throttling = False
        self.last_sent = None
        self.last_sent_pos = 0


    def connect(self):
        """ Connect to target. """
        with self.socket_lock:
            self.socket = socket.create_connection((self.hostname, self.port), timeout=self.CONNECT_TIMEOUT, source_address=self.source_address)
            if self.tls:
                self.setup_tls()

            # Make socket non-blocking, we are already told by the event loop when we can read and/or write without blocking.
            self.socket.setblocking(False)
            # Enable TCP keep-alive to keep the connection from timing out. This is strictly unnecessary as IRC already has in-band keepalive.
            if hasattr(socket, 'SO_KEEPALIVE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Reset message buffer and queue.
        with self.send_queue_lock:
            self.send_queue = collections.deque()
            self.unthrottled_sends = 0
            self.last_sent = 0
            self.last_sent_pos = 0

        # Add handlers.
        self.eventloop.register(self.socket.fileno())
        self.setup_handlers()


    def upgrade_to_tls(self, tls_verify=False, tls_certificate_file=None, tls_certificate_keyfile=None, tls_certificate_password=None):
        """ Uprade existing connection to TLS. """
        # Set local config options.
        self.tls = True
        self.tls_verify = False
        if tls_certificate_file:
            self.tls_certificate_file = tls_certificate_file
        if tls_certificate_keyfile:
            self.tls_certificate_keyfile = tls_certificate_keyfile
        if tls_certificate_password:
            self.tls_certificate_password = tls_certificate_password

        # Remove socket callbacks since the fd might change as the event loop sees it, setup TLS, and setup handlers again.
        self.remove_handlers()
        self.eventloop.unregister(self.socket.fileno())
        self.setup_tls()
        self.eventloop.register(self.socket.fileno())
        self.setup_handlers()

    def setup_tls(self):
        """ Transform our regular socket into a TLS socket. """
        # Create context manually, as we're going to set our own options.
        self.tls_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # Load client/server certificate.
        if self.tls_certificate_file:
            self.tls_context.load_cert_chain(self.tls_certificate_file, self.tls_certificate_keyfile, password=self.tls_certificate_password)

        # Set some relevant options:
        # - No server should use SSLv2 or SSLv3 any more, they are outdated and full of security holes. (RFC6176, RFC7568)
        # - Disable compression in order to counter the CRIME attack. (https://en.wikipedia.org/wiki/CRIME_%28security_exploit%29)
        # - Disable session resumption to maintain perfect forward secrecy. (https://timtaubert.de/blog/2014/11/the-sad-state-of-server-side-tls-session-resumption-implementations/)
        for opt in ['NO_SSLv2', 'NO_SSLv3', 'NO_COMPRESSION', 'NO_TICKET']:
            if hasattr(ssl, 'OP_' + opt):
                self.tls_context.options |= getattr(ssl, 'OP_' + opt)

        # Set TLS verification options.
        if self.tls_verify:
            # Set our custom verification callback, if the library supports it.
            if hasattr(self.tls_context, 'set_servername_callback'):
                self.tls_context.set_servername_callback(self.verify_tls)

            # Load certificate verification paths.
            self.tls_context.set_default_verify_paths()
            if sys.platform in DEFAULT_CA_PATHS and path.isdir(DEFAULT_CA_PATHS[sys.platform]):
                self.tls_context.load_verify_locations(capath=DEFAULT_CA_PATHS[sys.platform])

            # If we want to verify the TLS connection, we first need a certicate.
            # Check this certificate and its entire chain, if possible, against revocation lists.
            self.tls_context.verify_mode = ssl.CERT_REQUIRED
            if hasattr(self.tls_context, 'verify_flags'):
                self.tls_context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN

        self.socket = self.tls_context.wrap_socket(self.socket,
            # Send hostname over SNI, but only if our TLS library supports it.
            server_hostname=self.hostname if ssl.HAS_SNI else None)

        # Verify the peer certificate here if our TLS library doesn't have callback functionality.
        if self.tls_verify and not hasattr(self.tls_context, 'set_servername_callback'):
            self.verify_tls(self.socket, self.hostname, self.tls_context, as_callback=False)

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

    def disconnect(self):
        """ Disconnect from target. """
        if not self.connected:
            return

        # Remove handlers.
        self.remove_handlers()
        self.eventloop.unregister(self.socket.fileno())

        with self.socket_lock:
            if self.tls:
                self.teardown_tls()

            # This might give an error if the connection was already closed by the other end.
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except (OSError, IOError):
                pass
            self.socket.close()
            self.socket = None

        # Clear buffers.
        with self.send_queue_lock:
            self.send_queue = None
            self.unthrottled_sends = 0
            self.last_sent = None

    def teardown_tls(self):
        """ Tear down our TLS connection and give us our regular socket back. """
        # This might give an error if the connection was already closed by the other end.
        try:
            self.socket = self.socket.unwrap()
        except (OSError, IOError):
            pass


    @property
    def connected(self):
        """ Whether this connection is... connected to something. """
        return self.socket is not None

    def run_forever(self):
        """ Enter the IO loop. """
        self.setup_handlers()
        self.eventloop.run()
        self.remove_handlers()

    def stop(self):
        """ Stop event loop. """
        self.eventloop.schedule(lambda: self.eventloop.stop())


    ## Handler setup and teardown.

    def setup_handlers(self):
        """ Register underlying event loop handlers. """
        if not self.connected:
            return

        self.remove_handlers()
        with self.socket_lock:
            self.eventloop.on_read(self.socket.fileno(), self._on_read)
            self.eventloop.on_error(self.socket.fileno(), self._on_error)

        self.update_write_handler()

    def remove_handlers(self):
        """ Remove underlying event loop handlers. """
        if not self.connected:
            return

        with self.socket_lock:
            if self.eventloop.handles_read(self.socket.fileno(), self._on_read):
                self.eventloop.off_read(self.socket.fileno(), self._on_read)
            if self.eventloop.handles_write(self.socket.fileno(), self._on_write):
                self.eventloop.off_write(self.socket.fileno(), self._on_write)
            if self.eventloop.handles_error(self.socket.fileno(), self._on_error):
                self.eventloop.off_error(self.socket.fileno(), self._on_error)

    def update_write_handler(self):
        """
        Update underlying event loop to listen to write events if we have data to write,
        and stop listening if we have nothing to write or being throttled.
        """
        if not self.connected:
            return

        with self.send_queue_lock, self.socket_lock:
            # Only listen to write events if we aren't throttling our write handler.
            if self.send_queue and not self.throttling:
                if not self.eventloop.handles_write(self.socket.fileno(), self._on_write):
                    self.eventloop.on_write(self.socket.fileno(), self._on_write)
            else:
                if self.eventloop.handles_write(self.socket.fileno(), self._on_write):
                    self.eventloop.off_write(self.socket.fileno(), self._on_write)


    ## Lower-level data-related methods.

    def on(self, method, callback):
        """
        Add callback for event.

        Handlers are called as follows:
         - read: Called with the read data.
         - write: Called with the a list of the written messages.
         - error: Called with the exception that occurred.
        """
        if method not in self.handlers:
            raise ValueError('Given method must be one of: {}'.format(', '.join(self.handlers)))
        self.handlers[method].append(callback)

    def off(self, method, callback):
        """ Remove callback for event. """
        if method not in self.handlers:
            raise ValueError('Given method must be one of: {}'.format(', '.join(self.handlers)))
        self.handlers[method].remove(callback)

    def handles(self, method, callback):
        """ Determine whether or not event is currently handled by callback. """
        if method not in self.handlers:
            raise ValueError('Given method must be one of: {}'.format(', '.join(self.handlers)))
        return callback in self.handlers[method]

    def send(self, data):
        """ Add data to send queue. """
        with self.send_queue_lock:
            self.send_queue.append(data)
        self.update_write_handler()

    def _on_read(self, fd):
        with self.socket_lock:
            try:
                data = self.socket.recv(BUFFER_SIZE)
            except WOULD_BLOCK_ERRORS as e:
                # Nothing to do here.
                return
            except OSError as e:
                if e.errno not in WOULD_BLOCK_ERRNOS:
                    # Re-raise irrelevant errors.
                    raise
                # Nothing to do here.
                return

        if data == b'':
            # Some I/O notification backends use a zero-length read as error indicator.
            return self._on_error(fd)
        else:
            for handler in self.handlers['read']:
                handler(data)

    def _on_write(self, fd):
        sent_messages = []
        with self.send_queue_lock:
            # Keep sending while we can and have data left.
            while self.send_queue:
                current = time.time()
                # No writing if we're being throttled.
                if current < self.last_sent:
                    break

                # Do we need to throttle messages?
                if self.throttle and current - self.last_sent < MESSAGE_THROTTLE_DELAY:
                    if self.unthrottled_sends >= MESSAGE_THROTTLE_TRESHOLD:
                        # Enough unthrottled messages let through: introduce some delay.
                        self.throttling = True
                        self.eventloop.schedule_in(datetime.timedelta(seconds=self.last_sent + MESSAGE_THROTTLE_DELAY - current), self._unthrottle)
                        break
                    else:
                        # Allow message through, but note that the unthrottling should be recorded.
                        unthrottle = True
                else:
                    # No need to throttle.
                    unthrottle = False
                    self.unthrottled_sends = 0

                # Send as much data as we can.
                to_send = self.send_queue[0]
                with self.socket_lock:
                    try:
                        self.last_sent_pos += self.socket.send(to_send[self.last_sent_pos:])
                    except WOULD_BLOCK_ERRORS as e:
                        # Nothing more to do here.
                        break
                    except OSError as e:
                        if e.errno not in WOULD_BLOCK_ERRNOS:
                            # Re-raise irrelevant errors.
                            raise
                        # Nothing more to do here.
                        break

                if self.last_sent_pos != len(to_send):
                    # The message was not fully sent, so presume we can't send anymore.
                    break
                else:
                    sent_messages.append(self.send_queue.popleft())
                    # Throttling only counts if we sent a whole message.
                    self.last_sent = time.time()
                    self.last_sent_pos = 0
                    if unthrottle:
                        self.unthrottled_sends += 1

        # We might not need to listen for write events anymore if our queue is empty or if we're throttling.
        self.update_write_handler()

        if not sent_messages:
            return
        for handler in self.handlers['write']:
            handler(sent_messages)

    def _unthrottle(self):
        self.unthrottled_sends = 0
        self.throttling = False
        self.update_write_handler()

    def _on_error(self, fd):
        # Get native error and create exception from it.
        errno = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        try:
            message = os.strerror(errno)
        except ValueError:
            message = 'Unknown error'
        exception = IOError(errno, message)

        for handler in self.handlers['error']:
            handler(exception)
