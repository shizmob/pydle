## _args.py
# Common argument parsing code.
import argparse
import functools
import logging
import pydle

def client_from_args(name, description, default_nick='Bot', cls=pydle.Client):
    # Parse some arguments.
    parser = argparse.ArgumentParser(name, description=description, add_help=False,
        epilog='This program is part of {package}.'.format(package=pydle.__name__))

    meta = parser.add_argument_group('Meta')
    meta.add_argument('-h', '--help', action='help', help='What you are reading right now.')
    meta.add_argument('-v', '--version', action='version', version='{package}/%(prog)s {ver}'.format(package=pydle.__name__, ver=pydle.__version__), help='Dump version number.')
    meta.add_argument('-V', '--verbose', help='Be verbose in warnings and errors.', action='store_true', default=False)
    meta.add_argument('-d', '--debug', help='Show debug output.', action='store_true', default=False)

    conn = parser.add_argument_group('Connection')
    conn.add_argument('server', help='The server to connect to.', metavar='SERVER')
    conn.add_argument('-p', '--port', help='The port to use. (default: 6667, 6697 (TLS))')
    conn.add_argument('-P', '--password', help='Server password.', metavar='PASS')
    conn.add_argument('--tls', help='Use TLS. (default: no)', action='store_true', default=False)
    conn.add_argument('--verify-tls', help='Verify TLS certificate sent by server. (default: no)', action='store_true', default=False)
    conn.add_argument('-e', '--encoding', help='Connection encoding. (default: UTF-8)', default='utf-8', metavar='ENCODING')

    init = parser.add_argument_group('Initialization')
    init.add_argument('-n', '--nickname', help='Nickname. Can be set multiple times to set fallback nicknames. (default: {})'.format(default_nick), action='append', dest='nicknames', default=[], metavar='NICK')
    init.add_argument('-u', '--username', help='Username. (default: derived from nickname)', metavar='USER')
    init.add_argument('-r', '--realname', help='Realname (GECOS). (default: derived from nickname)', metavar='REAL')
    init.add_argument('-c', '--channel', help='Channel to automatically join. Can be set multiple times for multiple channels.', action='append', dest='channels', default=[], metavar='CHANNEL')

    auth = parser.add_argument_group('Authentication')
    auth.add_argument('--sasl-identity', help='Identity to use for SASL authentication. (default: <empty>)', default='', metavar='SASLIDENT')
    auth.add_argument('--sasl-username', help='Username to use for SASL authentication.', metavar='SASLUSER')
    auth.add_argument('--sasl-password', help='Password to use for SASL authentication.', metavar='SASLPASS')
    auth.add_argument('--sasl-mechanism', help='Mechanism to use for SASL authentication.', metavar='SASLMECH')
    auth.add_argument('--tls-client-cert', help='TLS client certificate to use.', metavar='CERT')
    auth.add_argument('--tls-client-cert-keyfile', help='Keyfile to use for TLS client cert.', metavar='KEYFILE')

    args = parser.parse_args()

    # Set nicknames straight.
    if not args.nicknames:
        nick = default_nick
        fallback = []
    else:
        nick = args.nicknames.pop(0)
        fallback = args.nicknames

    # Set log level.
    if args.debug:
        log_level = logging.DEBUG
    elif not args.verbose:
        log_level = logging.ERROR

    logging.basicConfig(level=log_level)

    # Setup client and connect.
    client = cls(nickname=nick, fallback_nicknames=fallback, username=args.username, realname=args.realname,
        sasl_identity=args.sasl_identity, sasl_username=args.sasl_username, sasl_password=args.sasl_password, sasl_mechanism=args.sasl_mechanism,
        tls_client_cert=args.tls_client_cert, tls_client_cert_key=args.tls_client_cert_keyfile)

    connect = functools.partial(client.connect,
        hostname=args.server, port=args.port, password=args.password, encoding=args.encoding,
        channels=args.channels, tls=args.tls, tls_verify=args.verify_tls
    )

    return client, connect
