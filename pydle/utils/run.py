## run.py
# Run client.
import pydle
from . import _args

def main():
    client = _args.client_from_args('pydle', description='pydle IRC library.')
    client.handle_forever()

if __name__ == '__main__':
    main()
