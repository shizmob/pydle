try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

import pydle
from .mocks import MockServer, MockClient, MockConnection, MockEventLoop, MockMessage, mock_create_message, mock_has_message, mock_parse_message


def with_client(*features, connected=True, messages=True):
    if not features:
        features = (pydle.client.BasicClient,)
    if features not in with_client.classes:
        with_client.classes[features] = pydle.featurize(MockClient, *features)

    def inner(f):
        def run():
            server = MockServer()
            client = with_client.classes[features]('TestcaseRunner', mock_server=server)
            if connected:
                client.connect('mock://local', 1337, eventloop=MockEventLoop())
            if messages:
                client._create_message = mock_create_message
                client._has_message = mock_has_message
                client._parse_message = mock_parse_message

            try:
                ret = f(client=client, server=server)
                return ret
            finally:
                if client.eventloop:
                    client.eventloop.stop()

        run.__name__ = f.__name__
        return run
    return inner

with_client.classes = {}
