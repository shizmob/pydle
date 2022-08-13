## run.py
# Run client.
import asyncio
from . import _args


def main():
    client, connect = _args.client_from_args('pydle', description='pydle IRC library.')
    asyncio.run(connect())


if __name__ == '__main__':
    main()
