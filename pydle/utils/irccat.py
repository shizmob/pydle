#!/usr/bin/env python3
## irccat.py
# Simple threaded irccat implementation, using pydle.
import sys
import logging
import asyncio

from .. import Client, __version__
from . import _args


class IRCCat(Client):
    """ irccat. Takes raw messages on stdin, dumps raw messages to stdout. Life has never been easier. """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.async_stdin = None

    async def _send(self, data):
        await super()._send(data)

    async def process_stdin(self):
        """ Yes. """
        loop = asyncio.get_event_loop()

        self.async_stdin = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self.async_stdin)
        await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

        while True:
            line = await self.async_stdin.readline()
            if not line:
                break
            await self.raw(line.decode('utf-8'))

        await self.quit('EOF')

    async def on_raw(self, message):
        print(message._raw)
        await super().on_raw(message)

    async def on_ctcp_version(self, source, target, contents):
        await self.ctcp_reply(source, 'VERSION', 'pydle-irccat v{}'.format(__version__))


async def _main():
    # Create client.
    irccat, connect = _args.client_from_args('irccat', default_nick='irccat',
                                             description='Process raw IRC messages from stdin, dump received IRC messages to stdout.',
                                             cls=IRCCat)
    await connect()
    while True:
        await irccat.process_stdin()


def main():
    # Setup logging.
    logging.basicConfig(format='!! %(levelname)s: %(message)s')
    asyncio.run(_main())


if __name__ == '__main__':
    main()
