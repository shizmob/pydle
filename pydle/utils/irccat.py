#!/usr/bin/env python3
## irccat.py
# Simple threaded irccat implementation, using pydle.
import sys
import threading
import logging

from .. import Client, __version__
from . import _args


class IRCCat(Client):
    """ irccat. Takes raw messages on stdin, dumps raw messages to stdout. Life has never been easier. """

    def _send(self, data):
        sys.stdout.write(data)
        super()._send(data)

    def process_stdin_forever(self):
        """ Yes. """
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            self.raw(line)

    def on_raw(self, message):
        print(message._raw)
        super().on_raw(message)

    def on_ctcp_version(self, source, target, contents):
        self.ctcp_reply(source, 'VERSION', 'pydle-irccat v{}'.format(__version__))


def main():
    # Setup logging.
    logging.basicConfig(format='!! %(levelname)s: %(message)s')

    # Create client.
    irccat = _args.client_from_args('irccat', default_nick='irccat', description='Process raw IRC messages from stdin, dump received IRC messages to stdout.', cls=IRCCat)

    thread = None
    if irccat.connected:
        # Let's rock.
        thread = threading.Thread(target=irccat.handle_forever)
        thread.start()

        # Process input in main thread.
        irccat.process_stdin_forever()

    # Other thread is done. Let's disconnect.
    irccat.quit('EOF on standard input')
    if thread:
        thread.join()

if __name__ == '__main__':
    main()
