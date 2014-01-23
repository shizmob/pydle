## nickserv.py
# Support automatic NickServ authentication.
from .. import client

__all__ = [ 'NickServSupport' ]


class NickServSupport(client.BasicClient):
    """ Support for NickServ authentication. """

    ## Internal overrides.

    def __init__(self, *args, nickserv_password=None, **kwargs):
        self.__init__(*args, **kwargs)
        self.nickserv_password = nickserv_password

