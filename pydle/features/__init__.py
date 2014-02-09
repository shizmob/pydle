from . import rfc1459, ctcp, tls, isupport, whox, ircv3_1, ircv3_2

from .rfc1459 import RFC1459Support
from .ctcp import CTCPSupport
from .tls import TLSSupport
from .isupport import ISUPPORTSupport
from .whox import WHOXSupport
from .ircv3_1 import IRCv3_1Support
from .ircv3_2 import IRCv3_2Support

ALL = [ IRCv3_1Support, IRCv3_2Support, WHOXSupport, ISUPPORTSupport, CTCPSupport, TLSSupport, RFC1459Support ]
LITE = [ WHOXSupport, ISUPPORTSupport, CTCPSupport, TLSSupport, RFC1459Support ]
