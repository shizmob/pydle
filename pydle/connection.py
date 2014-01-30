import sys
import os.path as path
import itertools

import socket
import ssl
import select

import errno
import collections
import threading

from . import protocol

__all__ = [ 'BUFFER_SIZE', 'TIMEOUT', 'NotConnected', 'NoMessageAvailable', 'Connection' ]


DEFAULT_CA_PATHS = {
    'linux': '/etc/ssl/certs',
    'linux2': '/etc/ssl/certs',
    'freebsd': '/etc/ssl/certs'
}

BUFFER_SIZE = 4096
TIMEOUT = 0.5


class NotConnected(Exception):
    pass

class NoMessageAvailable(Exception):
    pass


class Connection:
    """ A TCP connection over the IRC protocol. """
    CONNECT_TIMEOUT = 10

    def __init__(self, hostname, port, tls=False, tls_verify=True, encoding='utf-8', tls_certificate_file=None, tls_certificate_keyfile=None, ping_timeout=240):
        self.hostname = hostname
        self.port = port
        self.ping_timeout = ping_timeout
        self.encoding = encoding

        self.tls = tls
        self.tls_context = None
        self.tls_verify = tls_verify
        self.tls_certificate_file = tls_certificate_file
        self.tls_certificate_keyfile = tls_certificate_keyfile

        self.timer = None
        self.timer_lock = threading.RLock()
        self.socket = None
        self.socket_lock = threading.RLock()
        self.buffer = None
        self.buffer_lock = threading.RLock()
        self.message_queue = None
        self.message_lock = threading.RLock()

    def connect(self):
        """ Connect to target. """
        with self.socket_lock:
            # Create regular socket.
            self.socket = socket.create_connection((self.hostname, self.port), timeout=self.CONNECT_TIMEOUT)

            # Wrap it in a TLS socket if we have to.
            if self.tls:
                self.setup_tls()

            self.socket.settimeout(TIMEOUT)
            # Enable keep-alive.
            if hasattr(socket, 'SO_KEEPALIVE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Have the socket return an error instead of signaling SIGPIPE.
            if hasattr(socket, 'SO_NOSIGPIPE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_NOSIGPIPE, 1)

        # Reset message buffer and queue.
        with self.buffer_lock:
            self.buffer = b''
        with self.message_lock:
            self.message_queue = collections.deque()

    def setup_tls(self):
        """ Transform our regular socket into a TLS socket. """
        # Set up context.
        self.tls_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

        # Load client/server certificate.
        if self.tls_certificate_file:
            self.tls_context.load_cert_chain(self.tls_certificate_file, self.tls_certificate_keyfile)

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
                self.tls_context.load_verify_locations(ca_path=DEFAULT_CA_PATHS[sys.platform])

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

        with self.socket_lock:
            if self.tls:
                self.teardown_tls()

            # This might give an error if the connection was already closed by the other end.
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None

        # Clear buffers and queues.
        with self.buffer_lock:
            self.buffer = None
        with self.message_lock:
            self.message_queue = None

    def teardown_tls(self):
        """ Tear down our TLS connection and give us our regular socket back. """
        # This might give an error if the connection was already closed by the other end.
        try:
            self.socket = self.socket.unwrap()
        except OSError:
            pass


    @property
    def connected(self):
        """ Whether this connection is... connected to something. """
        return self.socket is not None


    ## High-level message-related methods.

    def generate_messages(self):
        """ Create an iterator out of this connection which will blockingly generate messages as they come. """
        return iter(self)

    def has_message(self, types=None):
        """ Determine if this connection has a message ready for processing. """
        # Low-hanging fruit: is there a message ready in the queue?
        if len(self.message_queue) > 0:
            # Is the message of the type we want?
            if types:
                with self.message_lock:
                    for source, command, params in reversed(self.message_queue):
                        if command in types:
                            return True
                    else:
                        return False
            # Any message is fine.
            return True

        # See if we have data that isn't parsed yet.
        if self.has_data() and self.receive_data():
            added = self.parse_data()

            # Run again if we're looking for specific types, else it's all good.
            if added and types:
                return self.has_message(types=types)
            # Any added message is fine.
            return added

        return False

    def get_message(self, types=None, retry=False):
        """ Get an IRC message for processing. """
        with self.message_lock:
            try:
                # Looking for specific type?
                if types:
                    # Iterate through messages and find relevant type.
                    for source, command, params in reversed(self.message_queue[:]):
                        if command in types:
                            self.message_queue.remove((source, command, params))
                            return source, command, params
                    else:
                        raise IndexError('Not in queue.')
                # Any type is fine.
                else:
                    message = self.message_queue.popleft()
            except IndexError:
                if retry or not self.has_data():
                    raise NoMessageAvailable('No message available.')

                # Try to parse any messages we have and try again.
                if not self.receive_data() or not self.parse_data():
                    raise NoMessageAvailable('No message available.')

                # New messages were added, let's fetch them.
                return self.get_message(types=types, retry=True)

        return message

    def send_message(self, command, *params, source=None):
         """ Send a message to the other endpoint. """
         message = protocol.construct(command, *params, source=source)
         return self.send_string(message)

    def wait_for_message(self, types=None):
        """ Wait until a message has arrived. """
        # No use waiting if we already have a message.
        if self.has_message(types=types):
            return

        if not self.connected:
            raise NotConnected('Not connected.')

        while True:
            try:
                select.select([ self.socket ], [], [])
            except Exception as e:
                self.disconnect()
                raise NotConnected('Error while select()ing on socket: ' + str(e))

            if self.has_message(types=types):
                break


    ## Iterator stuff.

    def __iter__(self):
        """ Create an iterator out of this pool that will blockingly generate messages as they come. """
        return self

    def __next__(self):
        """ Wait for next message to arrive and return it. """
        if not self.connected:
            raise StopIteration

        self.wait_for_message()
        return self.get_message()


    ## Lower-level data-related methods.

    def has_data(self):
        """ Check if socket has data. """
        if not self.connected:
            return False

        with self.socket_lock:
            try:
                readable, writable, error = select.select([ self.socket ], [], [], 0)
            except Exception as e:
                self.disconnect()
                raise NotConnected('Error while select()ing on socket: ' + str(e))

            return self.socket in readable


    def receive_data(self):
        """ Try and receive any data and process it. Will return True if new data was added. """
        if not self.has_data():
            return False

        if hasattr(socket, 'MSG_NOSIGNAL'):
            flags = socket.MSG_NOSIGNAL
        else:
            flags = 0

        data = b''
        with self.socket_lock:
            try:
                data = self.socket.recv(BUFFER_SIZE, flags)
                # No data while select() indicates we have data available means the other party has closed the socket.
                if not data:
                    self.disconnect()
            except OSError as e:
                 if hasattr(errno, 'EAGAIN') and e.errno == errno.EAGAIN:
                     return self.receive_data()
                 raise

        if data:
            with self.buffer_lock:
                self.buffer += data
            return True
        return False

    def extract_data(self):
        """ Extract lines from current data. """
        # Some IRC servers use only \n as the line separator, so use that.
        sep = protocol.MINIMAL_LINE_SEPARATOR.encode('us-ascii')

        # Extract message lines from buffer.
        with self.buffer_lock:
            if not sep in self.buffer:
                return False

            lines = [ line + sep for line in self.buffer.split(sep) ]
            # Put last line (the remainder) back into the buffer, minus the added separator.
            self.buffer = lines.pop()[:-len(sep)]

        return lines

    def parse_data(self):
        """ Attempt to parse existing data into IRC messages. Will return True if new messages were added. """
        lines = self.extract_data()

        # Parse messages and put them into the message queue.
        with self.message_lock:
            for line in lines:
                # Parse message.
                try:
                    parsed = protocol.parse(line, encoding=self.encoding)
                except protocol.ProtocolViolation:
                    # TODO: Notification.
                    continue

                self.message_queue.append(parsed)

        return True

    def send_string(self, string):
        """ Send raw string to other end point. """
        self.send_data(string.encode(self.encoding))

    def send_data(self, data):
        """ Send raw data to other end point. """
        sent = 0

        if not self.connected:
            raise NotConnected('Not connected.')

        with self.socket_lock:
            # Continue until all data has been sent.
            while sent < len(data):
                try:
                    sent += self.socket.send(data[sent:])
                except OSError as e:
                    if hasattr(errno, 'EAGAIN') and e.errno == errno.EAGAIN:
                        continue
                    raise


class ConnectionPool:
    """ A pool of connections. """
    def __init__(self, conns=None):
        if not conns:
            conns = []

        self.connections = set(conns)
        self.connection_cycle = itertools.cycle(self.connections)
        self.index = 0

    def add(self, connection):
        """ Add connection to pool. """
        self.connections.add(connection)
        self.connection_cycle = itertools.cycle(self.connections)

    def remove(self, connection):
        self.connections.remove(connection)
        self.connection_cycle = itertools.cycle(self.connections)


    ## High-level message stuff.

    def generate_messages(self):
        """ Create an iterator out of this pool which will blockingly generate messages as they come. """
        return iter(self)

    def has_message(self):
        """ Check if any connection has messages available. """
        return any(conn.has_message() for conn in self.connections)

    def get_message(self):
        """
        Get first available message from any connection. Returns a (connection, message) tuple.
        Tries to be fair towards connections by cycling the start connection it tries to take a message from.
        """
        if not self.has_message():
            raise NoMessageAvailable('No message available.')

        for conn in self.connection_cycle:
            if conn.has_message():
                return (conn, conn.get_message())

    def wait_for_message(self):
        """ Wait until any connection has a message available. """
        sockets = { conn.socket: conn for conn in self.connections if conn.connected }
        found = False

        if self.has_message():
            return

        while not found:
            # Wait forever until a socket becomes readable.
            readable, writable, error = select.select(sockets.keys(), [], [])

            # Iterate and parse.
            for socket in readable:
                conn = sockets[socket]

                if conn.has_message():
                    found = True
                    break


    ## Lower-level data stuff.

    def has_data(self):
        """ Check if any socket has data available. """
        sockets = [ conn.socket for conn in self.connections if conn.connected ]

        readable, writable, error = select.select(sockets, [], [], 0)
        return len(readable) > 0


    ## Iterator stuff.

    def __iter__(self):
        """ Create an iterator out of this pool that will blockingly generate messages as they come. """
        return self

    def __next__(self):
        """ Wait for next message to arrive and return it. """
        self.wait_for_message()
        return self.get_message()

