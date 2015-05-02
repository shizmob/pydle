from . import rfc1459, account, ctcp, tls, isupport, whox, ircv3

from .rfc1459 import RFC1459Support
from .account import AccountSupport
from .ctcp import CTCPSupport
from .tls import TLSSupport
from .isupport import ISUPPORTSupport
from .whox import WHOXSupport
from .ircv3 import IRCv3Support, IRCv3_1Support, IRCv3_2Support

ALL = [ IRCv3Support, WHOXSupport, ISUPPORTSupport, CTCPSupport, AccountSupport, TLSSupport, RFC1459Support ]
LITE = [ WHOXSupport, ISUPPORTSupport, CTCPSupport, TLSSupport, RFC1459Support ]
