# noinspection PyUnresolvedReferences
from asyncio import coroutine, Future
from functools import cmp_to_key
from . import connection, protocol, client, features
from .client import Error, NotInChannel, AlreadyInChannel, BasicClient, ClientPool
from .features.ircv3.cap import (
    NEGOTIATING as CAPABILITY_NEGOTIATING,
    FAILED as CAPABILITY_FAILED,
    NEGOTIATED as CAPABILITY_NEGOTIATED,
)


__name__ = "pydle"
__version__ = "0.9.4rc1"
__version_info__ = (0, 9, 4)
__license__ = "BSD"


def featurize(*features):
    """Put features into proper MRO order."""

    def compare_subclass(left, right):
        if issubclass(left, right):
            return -1
        if issubclass(right, left):
            return 1
        return 0

    sorted_features = sorted(features, key=cmp_to_key(compare_subclass))
    name = "FeaturizedClient[{features}]".format(
        features=", ".join(feature.__name__ for feature in sorted_features)
    )
    return type(name, tuple(sorted_features), {})


class Client(featurize(*features.ALL)):
    """A fully featured IRC client."""

    ...


class MinimalClient(featurize(*features.LITE)):
    """A cut-down, less-featured IRC client."""

    ...
