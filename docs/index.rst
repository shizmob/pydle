=====================================================
pydle - a Pythonic, extensible, compliant IRC library
=====================================================

pydle is a compact, flexible and standards-abiding IRC library for Python 3, written out of frustration with existing solutions.

Features
--------
- **Well-organized, easily extensible**

  Thanks to the modular setup, pydle's functionality is seperated in modules according to the standard they were defined in.
  This makes specific functionality trivial to find and decreases unwanted coupling,
  as well as allowing users to pick-and-choose the functionality they need.

  No spaghetti code.
- **Compliant**

  pydle contains modules, or "features" in pydle terminology, for almost every relevant IRC standard:

  * RFC1459_: The standard that defines the basic functionality of IRC - no client could live without.
  * TLS_: Support for chatting securely using TLS encryption.
  * CTCP_: The IRC Client-to-Client Protocol, allowing clients to query eachother for data.
  * ISUPPORT_: A method for the server to indicate non-standard or extended functionality to a client, and for clients to activate said functionality if needed.
  * WHOX_: Easily query status information for a lot of users at once.
  * IRCv3.1_: An ongoing effort to bring the IRC protocol to the twenty-first century, featuring enhancements such as extended capability negotiation and SASL authentication.
  * IRCv3.2_ *(in progress)*: The next, in-development iteration of IRCv3. Features among others advanced message tagging, a generalized metadata system, and online status monitoring.

  No half-assing functionality.
- **Asynchronous**

  IRC is an asychronous protocol; it only makes sense a clients that implements it is asynchronous as well. Built on top of the wonderful Tornado_ library, pydle relies on proven technologies to deliver proper high-performance asynchronous functionality and primitives.
  pydle allows using Futures to make asynchronous programming just as intuitive as doing regular blocking operations.

  No callback spaghetti.
- **Liberally licensed**

  The 3-clause BSD license ensures you can use pydle whenever, for what purpose you want.

  No arbitrary restrictions.

.. _RFC1459: https://tools.ietf.org/html/rfc1459.html
.. _TLS: https://tools.ietf.org/html/rfc5246
.. _CTCP: http://www.irchelp.org/irchelp/rfc/ctcpspec.html
.. _ISUPPORT: https://tools.ietf.org/html/draft-hardy-irc-isupport-00
.. _WHOX: https://hg.quakenet.org/snircd/file/tip/doc/readme.who
.. _IRCv3.1: http://ircv3.org/
.. _IRCv3.2: http://ircv3.org/
.. _Tornado: http://tornadoweb.org

Contents
--------
.. toctree::
   :maxdepth: 2

   intro
   usage
   features/index
   api/index
   licensing
