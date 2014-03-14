import pydle
from .mocks import MockServer, MockClient, MockEventLoop


def with_client(*features, connected=True, **options):
    if not features:
        features = (pydle.client.BasicClient,)
    if features not in with_client.classes:
        with_client.classes[features] = pydle.featurize(MockClient, *features)

    def inner(f):
        def run():
            server = MockServer()
            client = with_client.classes[features]('TestcaseRunner', mock_server=server, **options)
            if connected:
                client.connect('mock://local', 1337, eventloop=MockEventLoop())

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
