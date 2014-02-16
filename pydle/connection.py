import sys
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

__all__ = [ 'BUFFER_SIZE', 'TIMEOUT', 'NotConnected', 'NoMessageAvailable', 'Connection' ]


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


class NotConnected(Exception):
    pass

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
        self.throttling = False
        self.last_sent = None
        self.last_sent_pos = 0


    def connect(self):
        """ Connect to target. """
        with self.socket_lock:
            # Create regular socket.
            self.socket = socket.create_connection((self.hostname, self.port), timeout=self.CONNECT_TIMEOUT, source_address=self.source_address)

            # Wrap it in a TLS socket if we have to.
            if self.tls:
                self.setup_tls()

            # Make socket non-blocking.
            self.socket.setblocking(0)
            # Enable keep-alive.
            if hasattr(socket, 'SO_KEEPALIVE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Have the socket return an error instead of signaling SIGPIPE.
            if hasattr(socket, 'SO_NOSIGPIPE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_NOSIGPIPE, 1)

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
        # Set up context.
        self.tls_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # Load client/server certificate.
        if self.tls_certificate_file:
            self.tls_context.load_cert_chain(self.tls_certificate_file, self.tls_certificate_keyfile, password=self.tls_certificate_password)

        # Set some relevant options.
        # No server should use SSLv2 any more, it's outdated and full of security holes.
        # Disable compression to counter the CRIME attack. (https://en.wikipedia.org/wiki/CRIME_%28security_exploit%29)
        for opt in [ 'NO_SSLv2', 'NO_COMPRESSION']:
            if hasattr(ssl, 'OP_' + opt):
                self.tls_context.options |= getattr(ssl, 'OP_' + opt)

        # Set TLS verification options.
        if self.tls_verify:
            # Set our custom verification callback.
            if hasattr(self.tls_context, 'set_servername_callback'):
                self.tls_context.set_servername_callback(self.verify_tls)

            # Always set default root certificate storage paths.
            self.tls_context.set_default_verify_paths()

            # Try OS-specific paths too in case the above failed.
            if sys.platform in DEFAULT_CA_PATHS and path.isdir(DEFAULT_CA_PATHS[sys.platform]):
                self.tls_context.load_verify_locations(capath=DEFAULT_CA_PATHS[sys.platform])

            # Enable verification.
            self.tls_context.verify_mode = ssl.CERT_REQUIRED
            # Verify the entire chain if possible.
            if hasattr(self.tls_context, 'verify_flags'):
                self.tls_context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN

        # Wrap socket into a snuggly TLS blanket.
        self.socket = self.tls_context.wrap_socket(self.socket,
            # Send hostname over SNI, but only if our TLS library supports it.
            server_hostname=self.hostname if ssl.HAS_SNI else None)

        # And verify the peer here if our TLS library doesn't have callback functionality.
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
            ssl.match_hostname(cert, hostname)
        except ssl.CertificateError:
            if not as_callback:
                raise

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


    ## Handler setup and teardown.

    def setup_handlers(self):
        if not self.connected:
            return

        self.remove_handlers()
        with self.socket_lock:
            self.eventloop.on_read(self.socket.fileno(), self._on_read)
            self.eventloop.on_error(self.socket.fileno(), self._on_error)

        self.update_write_handler()

    def remove_handlers(self):
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
        if not self.connected:
            return

        with self.send_queue_lock, self.socket_lock:
            if self.send_queue and not self.throttling:
                if not self.eventloop.handles_write(self.socket.fileno(), self._on_write):
                    self.eventloop.on_write(self.socket.fileno(), self._on_write)
            else:
                if self.eventloop.handles_write(self.socket.fileno(), self._on_write):
                    self.eventloop.off_write(self.socket.fileno(), self._on_write)


    ## Lower-level data-related methods.

    def on(self, method, callback):
        """ Add callback for event. """
        if method not in self.handlers:
            raise ValueError('Given method must be one of: {}'.format(', '.join(self.handlers)))
        self.handlers[method].append(callback)

    def off(self, method, callback):
        """ Remove callback for event. """
        if method not in self.handlers:
            raise ValueError('Given method must be one of: {}'.format(', '.join(self.handlers)))
        self.handlers[method].remove(callback)

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
            return self._on_error(fd)
        else:
            for handler in self.handlers['read']:
                handler(data)

    def _on_write(self, fd):
        sent_messages = []
        with self.send_queue_lock:
            # ssl.SSLSocket does not allow any flags to be added to send().
            if not tls and hasattr(socket, 'MSG_NOSIGNAL'):
                send_flags = socket.MSG_NOSIGNAL
            else:
                send_flags = 0

            # Keep sending while we can and have data left.
            while self.send_queue:
                current = time.time()
                # No writing if we're being throttled.
                if current < self.last_sent:
                    break

                # Do we need to throttle messages?
                if current - self.last_sent < MESSAGE_THROTTLE_DELAY:
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
                        sent = self.socket.send(to_send, send_flags)
                    except WOULD_BLOCK_ERRORS as e:
                        # Nothing more to do here.
                        break
                    except OSError as e:
                        if e.errno not in WOULD_BLOCK_ERRNOS:
                            # Re-raise irrelevant errors.
                            raise
                        # Nothing more to do here.
                        break

                self.last_sent_pos += sent
                fully_sent = (self.last_sent_pos == len(to_send))

                if not fully_sent:
                    # The message was not fully sent, so presume we can't send anymore.
                    break
                else:
                    sent_messages.append(self.send_queue.popleft())
                    # Throttling only counts if we sent a whole message.
                    self.last_sent = time.time()
                    self.last_sent_pos = 0
                    if unthrottle:
                        self.unthrottled_sends += 1

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
        for handler in self.handlers['error']:
            handler()
