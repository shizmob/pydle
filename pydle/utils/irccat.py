#!/usr/bin/env python3
## irccat.py
# Simple threaded irccat implementation, using pydle.
import sys
import os
import threading
import logging
import asyncio
from asyncio.streams import FlowControlMixin

from .. import  Client, __version__
from . import _args
import asyncio

class IRCCat(Client):
    """ irccat. Takes raw messages on stdin, dumps raw messages to stdout. Life has never been easier. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.async_stdin = None

    @asyncio.coroutine
    def _send(self, data):
        sys.stdout.write(data)
        yield from super()._send(data)

    @asyncio.coroutine
    def process_stdin(self):
        """ Yes. """
        loop = self.eventloop.loop

        self.async_stdin = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self.async_stdin)
        yield from loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

        while True:
            line = yield from self.async_stdin.readline()
            if not line:
                break
            yield from self.raw(line.decode('utf-8'))

        yield from self.quit('EOF')

    @asyncio.coroutine
    def on_raw(self, message):
        print(message._raw)
        yield from super().on_raw(message)

    @asyncio.coroutine
    def on_ctcp_version(self, source, target, contents):
        self.ctcp_reply(source, 'VERSION', 'pydle-irccat v{}'.format(__version__))


def main():
    # Setup logging.
    logging.basicConfig(format='!! %(levelname)s: %(message)s')

    # Create client.
    irccat, connect = _args.client_from_args('irccat', default_nick='irccat', description='Process raw IRC messages from stdin, dump received IRC messages to stdout.', cls=IRCCat)

    irccat.eventloop.schedule_async(connect())
    irccat.eventloop.run_with(irccat.process_stdin())


if __name__ == '__main__':
    main()
