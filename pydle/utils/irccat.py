#!/usr/bin/env python3
## irccat.py
# Simple threaded irccat implementation, using pydle.
import sys
import threading
import logging

from .. import features
from .. import protocol

from .. import featurize, __version__
from . import _args


class IRCCat(featurize(*features.ALL)):
    """ irccat. Takes raw messages on stdin, dumps raw messages to stdout. Life has never been easier. """
    def _get_message(self, types=None):
        """ Get message and print it to stdout. """
        message = self.connection.get_message(types=types)
        sys.stdout.write(message.construct(force=True))
        return message

    def _send_message(self, message):
        sys.stdout.write(message.construct(force=True))
        super()._send_message(message)

    def _send_raw(self, raw):
        sys.stdout.write(raw)
        super()._send_raw(raw)

    def process_stdin_forever(self):
        """ Yes. """
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            self.raw(line)

    def on_ctcp_version(self, source, target):
        self.ctcp_reply(source, 'VERSION', 'pydle-irccat v{}'.format(__version__))


def main():
    logging.basicConfig(format='!! %(levelname)s: %(message)s')

    # Create client.
    irccat = _args.client_from_args('irccat', default_nick='irccat', description='Process raw IRC messages from stdin, dump received IRC messages to stdout.', cls=IRCCat)

    thread = None
    if irccat.connected:
        # Let's rock.
        thread = threading.Thread(target=irccat.poll_forever)
        thread.start()

        # Process input in main thread.
        irccat.process_stdin_forever()

    # Other thread is done. Let's disconnect.
    irccat.quit('EOF on standard input')
    if thread:
        thread.join()

if __name__ == '__main__':
    main()
