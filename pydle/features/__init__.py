__all__ = [
    "ALL",
    "AccountSupport",
    "CTCPSupport",
    "IRCv3Support",
    "IRCv3_1Support",
    "IRCv3_2Support",
    "ISUPPORTSupport",
    "LITE",
    "RFC1459Support",
    "RplWhoisHostSupport",
    "TLSSupport",
    "WHOXSupport",
    "account",
    "ctcp",
    "ircv3",
    "isupport",
    "rfc1459",
    "tls",
    "whox",
]

from . import account, ctcp, ircv3, isupport, rfc1459, tls, whox
from .account import AccountSupport
from .ctcp import CTCPSupport
from .ircv3 import IRCv3_1Support, IRCv3_2Support, IRCv3Support
from .isupport import ISUPPORTSupport
from .rfc1459 import RFC1459Support
from .rpl_whoishost import RplWhoisHostSupport
from .tls import TLSSupport
from .whox import WHOXSupport

ALL = [
    IRCv3Support,
    WHOXSupport,
    ISUPPORTSupport,
    CTCPSupport,
    AccountSupport,
    TLSSupport,
    RFC1459Support,
    RplWhoisHostSupport,
]
LITE = [WHOXSupport, ISUPPORTSupport, CTCPSupport, TLSSupport, RFC1459Support]
