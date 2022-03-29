import pytest
import pydle
from .mocks import MockClient
from .fixtures import with_client


def with_errorcheck_client(*features):
    def inner(f):
        def run():
            try:
                return with_client(*features, connected=False)(f)()
            except TypeError as e:
                assert False, e

        run.__name__ = f.__name__
        return run

    return inner


def assert_mro(client, *features):
    # Skip FeaturizedClient, MockClient, pydle.BasicClient and object classes.
    assert client.__class__.__mro__[2:-2] == features


class FeatureClass(pydle.BasicClient):
    pass


class SubFeatureClass(FeatureClass):
    pass


class SubBFeatureClass(FeatureClass):
    pass


class DiamondFeatureClass(SubBFeatureClass, SubFeatureClass):
    pass


@pytest.mark.asyncio
@with_errorcheck_client()
def test_featurize_basic(server, client):
    assert_mro(client)


@pytest.mark.asyncio
@with_errorcheck_client(FeatureClass)
def test_featurize_multiple(server, client):
    assert_mro(client, FeatureClass)


@pytest.mark.asyncio
@with_errorcheck_client(SubFeatureClass)
def test_featurize_inheritance(server, client):
    assert_mro(client, SubFeatureClass, FeatureClass)


@pytest.mark.asyncio
@with_errorcheck_client(FeatureClass, SubFeatureClass)
def test_featurize_inheritance_ordering(server, client):
    assert_mro(client, SubFeatureClass, FeatureClass)


@pytest.mark.asyncio
@with_errorcheck_client(SubBFeatureClass, SubFeatureClass, DiamondFeatureClass)
def test_featurize_inheritance_diamond(server, client):
    assert_mro(
        client, DiamondFeatureClass, SubBFeatureClass, SubFeatureClass, FeatureClass
    )
