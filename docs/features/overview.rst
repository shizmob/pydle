=================
Built-in features
=================
The following features are packaged with pydle and live in the :mod:`pydle.features` namespace.

RFC1459
=======
*API:* :class:`pydle.features.RFC1459Support`

RFC1459_ is the bread and butter of IRC: it is the standard that defines the very base concepts
of the IRC protocol, ranging from what a channel is to the basic commands to channel limits.
If you want your client to have actually any useful IRC functionality, it is recommend to include this feature.

.. _RFC1459: https://tools.ietf.org/html/rfc1459.html

Transport Layer Security (TLS)
==============================
*API:* :class:`pydle.features.TLSSupport`

Support for secure connections to the IRC server using `Transport Layer Security`_.

This allows, if the server supports it, for encrypted connections between the server and the client,
to prevent snooping and provide two-way authentication: both for the server to ensure its identity to the
client, and for the client to ensure its identity to the server.
The latter can also be used in certain service packages to automatically identify to the user account.

In order to connect to a TLS-enabled server, supply ``tls=True`` to :meth:`pydle.features.TLSSupport.connect`.

.. hint::
   pydle does not verify server-side TLS certificates by default; to enable certificate verification,
   supply ``tls_verify=True`` to :meth:`pydle.features.TLSSupport.connect` as well.

In order to supply a client certificate, :class:`pydle.features.TLSSupport` takes 3 additional constructor parameters:

 * ``tls_client_cert``: A path to the TLS client certificate.
 * ``tls_client_cert_key``: A path to the TLS client certificate key.
 * ``tls_client_cert_password``: The optional password for the certificate key.

.. _`Transport Layer Security`: https://tools.ietf.org/html/rfc5246

Client-to-Client Protocol (CTCP)
================================
*API:* :class:`pydle.features.CTCPSupport`

Support for encapsulation of out-of-band features into standard IRC messages using the `Client-to-Client Protocol`_.

This allows you to send meta-messages to other users, requesting e.g. their local time, client version, and more,
and respond to such requests. It adds `pydle.Client.ctcp(target, query, contents=None)`, which allows you to send a
CTCP request to a target, and `pydle.Client.ctcp_reply(target, query, contents=None)`, which allows you to respond to
CTCP requests.

In addition, it registers the `pydle.Client.on_ctcp(from, query, contents)` hook, which allows you to act upon *any* CTCP
request, and a per-type hook in the form of `pydle.Client.on_ctcp_<type>(from, contents)`, which allows you to act upon CTCP
requests of type `type`. `type` will always be lowercased. A few examples of `type` can be: `action`, `time`, `version`.

Finally, it registers the `pydle.Client.on_ctcp_reply(from, queyr, contents)` hook, which acts similar to the above hook,
except it is triggered when the client receives a CTCP response. It also registers `pydle.Client.on_ctcp_<type>_reply`, which
works similar to the per-type hook described above.

.. _`Client-to-Client Protocol`: http://www.irchelp.org/irchelp/rfc/ctcpspec.html

Server-side Extension Support (ISUPPORT)
========================================
*API:* :class:`pydle.features.ISUPPORTSupport`

Support for IRC protocol extensions using the `ISUPPORT`_ message.

This feature allows pydle to support protocol extensions which are defined using the non-standard `ISUPPORT` (005) message.
It includes built-in support for a number of popular `ISUPPORT`-based extensions, like `CASEMAPPING`, `CHANMODES`, `NETWORK`
and `PREFIX`.

It also provides the generic `pydle.Client.on_isupport_type(value)` hook, where `type` is the type of `ISUPPORT`-based
extension that the server indicated support for, and `value` is the optional value of said extension,
or `None` if no value was present.

.. _`ISUPPORT`: http://tools.ietf.org/html/draft-hardy-irc-isupport-00

Account System
==============
*API:* :class:`pydle.features.AccountSupport`

Support for a generic IRC account system.

Most IRC networks have some kind of account system that allows users to register and manage their nicknames and personas.
This feature provides additional support in pydle for this idea and its integration into the networks.

Currently, all it does is set the `identified` and `account` fields when doing a `WHOIS` query (`pydle.Client.whois(user)`) on
someone, which indicate if the target user has identified to their account, and if such, their account name, if available.

Extended User Tracking
======================
*API:* :class:`pydle.features.WHOXSupport`

Support for better user tracking using `WHOX`_.

This feature allows pydle to perform more accurate tracking of usernames, idents and account names, using the `WHOX`_ IRC
extension. This allows pydle's internal user database to be more accurate and up-to-date.

.. _`WHOX`: http://hg.quakenet.org/snircd/file/tip/doc/readme.who

IRCv3.1
=======
*API:* :class:`pydle.features.IRCv3_1Support`

IRCv3.1 support.

The `IRCv3 Working Group`_ is a working group organized by several network, server author, and client author representatives
with the intention to standardize current non-standard IRC practices better, and modernize certain parts of the IRC protocol.
The IRCv3 standards are specified as a bunch of extension specifications on top of the last widely-used IRC version, IRC v2.7,
also known as `RFC1459`_.

The `IRCv3.1 specification`_ adds useful features to IRC from a client perspective, including `SASL authentication`_,
support for `indicating when a user identified to their account`_, and `indicating when a user went away from their PC`_.

Including this feature entirely will activate all IRCv3.1 functionality for pydle. You can also opt-in to only select the two
major features of IRCv3.1, the capability negotiation framework and SASL authentication support, as described below,
by only including their features.

.. _`IRCv3 Working Group`: http://ircv3.org
   _`IRCv3.1 specification`: http://ircv3.org
   _`SASL authentication`: http://ircv3.org/extensions/sasl-3.1
   _`indicating when a user identified to their account`: http://ircv3.org/extensions/account-notify-3.1
   _`indicating when a user went away from their PC`: http://ircv3.org/extensions/away-notify-3.1

Capability Negotiation Support
------------------------------
*API:* :class:`pydle.features.ircv3_1.CapabilityNegotiationSupport`

Support for `capability negotiation` for IRC protocol extensions.

This feature enables support for a generic framework for negotiationg IRC protocol extension support between the client and the
server. It was quickly found that `ISUPPORT` alone wasn't sufficient, as it only advertises support from the server side instead
of allowing the server and client to negotiate. This is a generic base feature: enabling it on its own won't do much, instead
other features like the IRCv3.1 support feature, or the SASL authentication feature will rely on it to work.

This feature adds three generic hooks for feature authors whose features makes use of capability negotiation:

 * `pydle.Client.on_capability_<cap>_available()`: Called when the server indicates capability `cap` is available. Should return
    a boolean: whether or not to request the capability.
 * `pydle.Client.on_capability_<cap>_enabled()`: Called when the server has acknowledged the request of capability `cap`, and it
    has been enabled. Should return one of three values: `pydle.CAPABILITY_NEGOTIATING` when the capability will be further negotiated,
    `pydle.CAPABILITY_NEGOTIATED` when the capability has been negotiated successfully, or `pydle.CAPABILITY_FAILED` when negotiation
    of the capability has failed. If the function returned `pydle.CAPABILITY_NEGOTIATING`, it has to call
    `pydle.Client.capability_negotiated(cap, success=True)` when negotiating is finished.
 * `pydle.Client.on_capability_<cap>_disabled()`: Called when a previously-enabled capability `cap` has been disabled.

.. _`capability negotiation`: http://ircv3.org/specification/capability-negotiation-3.1

User Authentication Support (SASL)
----------------------------------
*API:* :class:`pydle.features.ircv3_1.SASLSupport`

Support for user authentication using `SASL`_.

This feature enables users to identify to their network account using the SASL protocol and practices. Three extra arguments are added
to the `pydle.Client` constructor:

 * `sasl_username`: The SASL username.
 * `sasl_password`: The SASL password.
 * `sasl_identity`: The identity to use. Default, and most common, is `''`.

These arguments are also set as attributes.

Currently, pydle's SASL support requires on the Python `pure-sasl`_ package and is limited to support for the `PLAIN` mechanism.

.. _`SASL`: https://tools.ietf.org/html/rfc4422
   _`pure-sasl`: https://github.com/thobbs/pure-sasl

IRCv3.2
=======
*API:* :class:`pydle.features.IRCv3_2Support`

Support for the IRCv3.2 specification.

The `IRCv3.2 specification`_ is the second iteration of specifications from the `IRCv3 Working Group`_. This set of specification is
still under development, and may change at any time. pydle's support is conservative, likely incomplete and to-be considered
experimental.

pydle currently supports the following IRCv3.2 extensions:

 * Indication of changed ident/host using `CHGHOST`_.
 * Indication of `ident and host` in RFC1459's /NAMES command response.
 * Monitoring of a user's online status using `MONITOR`_.
 * `Message tags`_ to add metadata to messages.

.. _`IRCv3 Working Group`: http://ircv3.org
   _`IRCv3.2 specification`: http://ircv3.org
   _`CHGHOST`: http://ircv3.org/extensions/chghost-3.2
   _`MONITOR`: http://ircv3.org/specification/monitor-3.2
   _`ident and host`: http://ircv3.org/extensions/userhost-in-names-3.2
   _`Message tags`: http://ircv3.org/specification/message-tags-3.2

As with the IRCv3.1 features, using this feature enables all of pydle's IRCv3.2 support. A user can also opt to only use individual
large IRCv3.2 features by using the features below.

Online Status Monitoring
------------------------
*API:* :class:`pydle.features.ircv3_2.MonitoringSupport`

Support for monitoring a user's online status.

This feature allows a client to monitor the online status of certain nicknames. It adds the `pydle.Client.monitor(nickname)` and
`pydle.Client.unmonitor(nickname)` APIs to add and remove nicknames from the monitor list.

If a monitored user comes online, `pydle.Client.on_user_online(nickname)` will be called. Similarly, if a user disappears offline,
`pydle.Client.on_user_offline(nickname)` will be called.

Tagged Messages
---------------
*API:* :class:`pydle.features.ircv3_2.TaggedMessageSupport`

Support for message metadata using tags.

This feature allows pydle to parse message metadata that is transmitted using 'tags'. Currently, this has no impact on any APIs
or hooks for client developers.
