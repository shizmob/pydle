from . import ctcp, tls, isupport, cap, sasl, ircv3_1

from .ctcp import CTCPSupport
from .tls import TLSSupport
from .isupport import ISUPPORTSupport
from .cap import CapabilityNegotiationSupport
from .sasl import SASLSupport
from .ircv3_1 import IRCv3_1Support
from .ircv3_2 import IRCv3_2Support

ALL = [ CTCPSupport, IRCv3_1Support, IRCv3_2Support, ISUPPORTSupport ]
LITE = [ CTCPSupport, ISUPPORTSupport ]
