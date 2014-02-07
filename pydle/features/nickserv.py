## nickserv.py
# Support automatic NickServ authentication.
from pydle.features import rfc1459

__all__ = [ 'NickServSupport' ]


class NickServSupport(rfc1459.RFC1459Support):
    """ Support for NickServ authentication. """

    ## Internal overrides.

    def __init__(self, *args, nickserv_password=None, **kwargs):
        self.__init__(*args, **kwargs)
        self.nickserv_password = nickserv_password

