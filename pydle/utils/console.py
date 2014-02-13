#!/usr/bin/env python3
## console.py
# Interactive console.
import threading
import code

import pydle
from . import _args

def main():
    client = _args.client_from_args('ipydle', description='Interactive pydle console.')

    # Let client do stuff in background.
    thread = threading.Thread(target=client.handle_forever)
    thread.start()

    # Run console.
    if client.connected:
        interp = code.InteractiveConsole({ 'self': client })
        interp.interact('{name} {ver} interactive console'.format(name=pydle.__name__, ver=pydle.__version__))
        # Kill off.
        client.quit()

    thread.join()

if __name__ == '__main__':
    main()
