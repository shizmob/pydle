## models.py
# User and channel model classes.
import warnings


class User:
    def __init__(self, client, nickname, realname=None, username=None, hostname=None):
        self.client = client
        self.nickname = nickname
        self.realname = realname
        self.username = username
        self.hostname = hostname

    @property
    def name(self):
        return self.nickname

    @property
    def hostmask(self):
        return '{n}!{u}@{h}'.format(n=self.nickname, u=self.username or '*', h=self.hostname or '*')

    def __getitem__(self, k):
        warnings.warn('Use of `user["attr"]` is deprecated. Please use `user.attr`.', DeprecationWarning)
        return getattr(self, k)

    def __setitem__(self, k, v):
        warnings.warn('Use of `user["attr"]` is deprecated. Please use `user.attr`.', DeprecationWarning)
        setattr(self, k, v)


class Channel:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.users = set()

    def __getitem__(self, k):
        warnings.warn('Use of `channel["attr"]` is deprecated. Please use `channel.attr`.', DeprecationWarning)
        return getattr(self, k)

    def __setitem__(self, k, v):
        warnings.warn('Use of `channel["attr"]` is deprecated. Please use `channel.attr`.', DeprecationWarning)
        setattr(self, k, v)


class Server:
    def __init__(self, name):
        self.name = name
