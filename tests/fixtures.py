import pydle
from .mocks import MockServer, MockClient


def with_client(*features, connected=True, **options):
    if not features:
        features = (pydle.client.BasicClient,)
    if features not in with_client.classes:
        with_client.classes[features] = pydle.featurize(MockClient, *features)

    def inner(f):
        async def run():
            server = MockServer()
            client = with_client.classes[features](
                "TestcaseRunner", mock_server=server, **options
            )
            if connected:
                await client.connect("mock://local", 1337)

        run.__name__ = f.__name__
        return run

    return inner


with_client.classes = {}
