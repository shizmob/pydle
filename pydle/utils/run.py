## run.py
# Run client.
import asyncio
import pydle
from . import _args

def main():
    client, connect = _args.client_from_args('pydle', description='pydle IRC library.')
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(connect(), loop=loop)
    loop.run_forever()

if __name__ == '__main__':
    main()
