## ircv3_3.py
# IRCv3.3 support (in progress).
from . import ircv3_2

__all__ = [ 'IRCv3_3Support' ]


class IRCv3_3Support(ircv3_2.IRCv3_2Support):
    """ Support for some of IRCv3.3's extensions. """

    ## IRC callbacks.

    async def on_capability_message_tags_available(self, value):
        """ Indicate that we can in fact parse arbitrary tags. """
        return True
