__all__ = [
    "AlreadyInChannel",
    "BasicClient",
    "CAPABILITY_FAILED",
    "CAPABILITY_NEGOTIATED",
    "CAPABILITY_NEGOTIATING",
    "Client",
    "ClientPool",
    "Error",
    "MinimalClient",
    "NotInChannel",
    "client",
    "connection",
    "features",
    "featurize",
    "protocol",
]

import importlib.metadata
from functools import cmp_to_key

from . import client, connection, features, protocol
from .client import AlreadyInChannel, BasicClient, ClientPool, Error, NotInChannel
from .features.ircv3.cap import (
    FAILED as CAPABILITY_FAILED,
)
from .features.ircv3.cap import (
    NEGOTIATED as CAPABILITY_NEGOTIATED,
)
from .features.ircv3.cap import (
    NEGOTIATING as CAPABILITY_NEGOTIATING,
)

__name__ = "pydle"
__version__ = importlib.metadata.version(__name__)
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
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
