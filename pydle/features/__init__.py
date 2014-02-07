from . import rfc1459, ctcp, tls, isupport, ircv3_1, ircv3_2

from .rfc1459 import RFC1459Support
from .ctcp import CTCPSupport
from .tls import TLSSupport
from .isupport import ISUPPORTSupport
from .ircv3_1 import IRCv3_1Support
from .ircv3_2 import IRCv3_2Support

ALL = [ CTCPSupport, IRCv3_1Support, IRCv3_2Support, ISUPPORTSupport, RFC1459Support ]
LITE = [ CTCPSupport, ISUPPORTSupport, RFC1459Support ]
