## nickserv.py
# Support automatic NickServ authentication.
from pydle.features import account

__all__ = [ 'NickServSupport' ]


class NickServSupport(account.AccountSupport):
    """ Support for NickServ authentication. """

    ## Internal overrides.

    def __init__(self, *args, nickserv_password=None, **kwargs):
        self.__init__(*args, **kwargs)
        self.nickserv_password = nickserv_password
