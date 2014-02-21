pydle
=====
Python IRC library.
-------------------

pydle is a compact, flexible and standards-abiding IRC library for Python 3.

Features
--------
* Compact: At ~2100SLoC at time of writing, it's not hard to find what you're looking for in the well-organized source code.
* Standards-abiding: Based on [RFC1459](https://tools.ietf.org/html/rfc1459.html) with some small extension tweaks, with full support of optional extension standards:
  - [TLS](http://tools.ietf.org/html/rfc5246)
  - [CTCP](http://www.irchelp.org/irchelp/rfc/ctcpspec.html)
  - (coming soon) [DCC](http://www.irchelp.org/irchelp/rfc/dccspec.html) and extensions
  - [ISUPPORT/PROTOCTL](http://tools.ietf.org/html/draft-hardy-irc-isupport-00)
  - [IRCv3.1](http://ircv3.atheme.org/)
  - (partial, in progress) [IRCv3.2](http://ircv3.atheme.org)
* Callback-based: IRC is an asynchronous protocol and so should a library that implements it be. Callbacks are used to process events from the server.
* Modularized and extensible: Features on top of RFC1459 are implemented as seperate modules for a user to pick and choose, and write their own. Broad features are written to be as extensible as possible.
* Liberally licensed: The 3-clause BSD license ensures you can use it everywhere.

Structure
---------
* `pydle.Client` - full-featured client that supports `pydle.BasicClient` plus all the features in `pydle.features`.
* `pydle.MinimalClient` - tinier client that supports `pydle.BasicClient` plus some features in `pydle.features`. (currently `ctcp`, `isupport` and `rfc1459`)
* `pydle.BasicClient` - base IRC message handler. Has no functionality.
* `pydle.ClientPool` - a 'pool' of several clients in order to handle multiple clients in one swift main loop.
* `pydle.EventLoop` - asynchronous event loop wrapper.
* `pydle.Future` - the future asynchronous primitive.
* `pydle.features` - IRC protocol implementations and extensions.
   - `pydle.features.rfc1459` - basic [RFC1459](https://tools.ietf.org/html/rfc1459.html) implementation with a few commonly-implemented [RF](https://tools.ietf.org/html/rfc2810.html)[C2](https://tools.ietf.org/html/rfc2811.html)[81](https://tools.ietf.org/html/rfc2812.html)[x](https://tools.ietf.org/html/rfc2813.html) extensions.
   - `pydle.features.account` - Basic features for an account system as implemented by services (in progress).
   - `pydle.features.ctcp` - [Client-to-Client Protocol](http://www.irchelp.org/irchelp/rfc/ctcpspec.html) support.
   - `pydle.features.tls` - [Transport Layer Security](https://tools.ietf.org/html/rfc5246.html) and [STARTTLS](https://ircv3.atheme.org/extensions/tls-3.1) support.
   - `pydle.features.isupport` - [ISUPPORT/PROTOCTL](http://tools.ietf.org/html/draft-hardy-irc-isupport-00) support.
   - `pydle.features.ircv3_1` - [IRCv3.1](http://ircv3.atheme.org) support.
      + `pydle.features.ircv3_1.cap` - [CAP](http://ircv3.atheme.org/specification/capability-negotiation-3.1) capability negotiation support.
      + `pydle.features.ircv3_1.sasl` - [Simple Authentication and Security Layer](http://ircv3.atheme.org/extensions/sasl-3.1) support - currently limited to the `PLAIN` mechanism.
      + `pydle.features.ircv3_1.ircv3_1` - [Miscellaneous](http://ircv3.atheme.org/extensions/multi-prefix-3.1) [features](http://ircv3.atheme.org/extensions/account-notify-3.1) [ensuring](http://ircv3.atheme.org/extensions/away-notify-3.1) [support](http://ircv3.atheme.org/extensions/extended-join-3.1) for [IRCv3.1](http://ircv3.atheme.org/).
   - `pydle.features.ircv3_2` - [IRCv3.2](http://ircv3.atheme.org) support (partial).
      + `pydle.features.ircv3_2.tags` - [Message Tagging](http://ircv3.atheme.org/specification/message-tags-3.2) support.
      + `pydle.features.ircv3_2.monitor` - [Online status monitoring](http://ircv3.atheme.org/specification/monitor-3.2) support.
      + `pydle.features.ircv3_2.ircv3_2` - [Miscellaneous](http://ircv3.atheme.org/extensions/userhost-in-names-3.2) features ensuring IRCv3.2 support.

Basic Usage
-----------
`python3 setup.py install`

From there, you can `import pydle` and subclass `pydle.Client` for your own functionality.

Setting a nickname and starting a connection over TLS:
```python
import pydle

# Simple echo bot.
class MyOwnBot(pydle.Client):
    def on_connect(self):
         self.join('#bottest')

    def on_message(self, source, target, message):
         self.message(target, message)

client = MyOwnBot('MyBot', realname='My Bot')
client.connect('irc.rizon.net', 6697, tls=True, tls_verify=False)
client.handle_forever()
```

*But wait, I want to handle multiple clients!*

No worries! Use `pydle.ClientPool` like such:
```python
pool = pydle.ClientPool()
for i in range(10):
    client = MyOwnBot('MyBot' + str(i))
    client.connect('irc.rizon.net', 6697, tls=True, tls_verify=False)
    pool.add(client)

# This will make sure all clients are treated in a fair way priority-wise.
pool.handle_forever()
```

If you want to customize bot features, you can subclass `pydle.BasicClient` and one or more features from `pydle.features` or your own feature classes, like such:
```python
# Only support RFC1459 (+small features), CTCP and our own ACME extension to IRC.
class MyFeaturedBot(pydle.features.ctcp.CTCPSupport, acme.ACMESupport, rfc1459.RFC1459Support):
    pass
```

To create your own features, just subclass from `pydle.BasicClient` and start adding callbacks for IRC messages:
```python
# Support custom ACME extension.
class ACMESupport(pydle.BasicClient):
    def on_raw_999(self, source, params):
        """ ACME's custom 999 numeric tells us to change our nickname. """
        nickname = params[0]
        self.set_nickname(nickname)
```

FAQ
---

**Q: When constructing my own client class from several base classes, I get the following error: _TypeError: Cannot create a consistent method resolution order (MRO) for bases X, Y, Z_. What causes this and how can I solve it?**

Pydle's use of class inheritance as a feature model may cause method resolution order conflicts if a feature inherits from a different feature, while a class inherits from both the original feature and the inheriting feature. To solve such problem, pydle offers a `featurize` function that will automatically put all classes in the right order and create an appropriate base class:
```python
# Purposely mis-ordered base classes, as SASLSupport inherits from CapabilityNegotiationSupport, but everything works fine.
MyBase = pydle.featurize(pydle.features.CapabilityNegotiationSupport, pydle.features.SASLSupport)
class Client(MyBase):
    pass
```

API
---

**pydle**

`featurize(*bases)`: create a client base class out of the given feature classes with a proper method resolution order. See the FAQ for details.

**pydle.Client**

`Client(nickname, fallback_nicknames=[], username=None, realname=None)` - construct a client. if `username`/`realname` are not given, they will be constructed from the nickname.

with `pydle.features.tls`, two extra keyword arguments are added:

- `tls_client_cert`: path to client certificate to use for TLS authentication;
- `tls_client_cert_key`: path to keyfile to use for `tls_client_cert`.

with `pydle.features.sasl`, three extra keyword arguments are added:

- `sasl_identity`: `AUTHZID` to use for SASL authentication. Default and most common option is `''` (empty);
- `sasl_username`: SASL username (`AUTHCID`);
- `sasl_password`: SASL password.

`Client.connect(host, port=None, encoding=pydle.protocol.DEFAULT_ENCODING)`- connect to server.

with `pydle.features.rfc1459`, an extra keyword argument is added:

- `password`: IRC password to use for server connection. Default is `None`.

with `pydle.features.tls`, two extra keyword arguments are added:

- `tls`: whether or not to use TLS for this connection. Default is `False`;
- `tls_verify`: whether or not to strictly verify the server certificate. Default is `False`.

`Client.disconnect()` - disconnect from server. If using `pydle.features.rfc1459`, `Client.quit(reason)` is preferred.

`Client.handle_forever()` - a 'main loop'-esque method. Will not return until the client disconnected.

*Attributes*

`Client.connected` - whether or not this client is connected.

`Client.connection` - the `pydle.connection.Connection` instance associated with this client.

`Client.eventloop` - the `pydle.async.EventLoop` instance for the client this thread is in.

`Client.logger` - the `pydle.logging.Logger` instance associated with this client.

`Client.nickname` - the current nickname. Changes will have no effect: use `Client.set_nickname(nick)`.

`Client.username` - the current username. Changes will only take effect on reconnect.

`Client.realname` - the current realname. Changes will only take effect on reconnect.

`Client.network` - set after connecting if sent by server. The IRC network this server belongs to.

`Client.server_tag` - a 'tag' to use for the currently connected to server.

`Client.users` - an informational dictionary about users the client knows about.

`Client.channels` - an informational dictionary about the channels the client is in.

with `pydle.features.rfc1459`, four extra attributes are added:

`Client.DEFAULT_QUIT_MESSAGE` - default quit message when `Client.quit()` is called without arguments.

`Client.registered` - whether or not this client has passed the IRC registration stage.

`Client.password` - the server password used for this connection. Changes will only take effect on reconnect.

`Client.motd` - set after connecting. The IRC server Message of the Day, if any.

with `pydle.features.tls`, two extra attributes are added:

- `Client.tls_client_cert` - file path to TLS client certificate to use;
- `Client.tls_client_cert_key` - file path to keyfile to use for `Client.tls_client_cert`.

with `pydle.features.sasl`, four extra attributes are added:

- `Client.SASL_TIMEOUT`: amount of seconds to wait for response from server before aborting SASL authentication.
- `Client.sasl_identity`: `AUTHZID` to use for SASL authentication. Default and most common option is `''` (empty);
- `Client.sasl_username`: SASL username (`AUTHCID`);
- `Client.sasl_password`: SASL password.

*IRC*

`Client.raw(message)` - send raw IRC command.

`Client.ping(identifier)` - ping server.

with `pydle.features.rfc1459`:

`Client.join(channel, password=None)` - join channel.

`Client.part(channel, reason=None)` - part channel.

`Client.cycle(channel)` - rejoin channel.

`Client.kick(channel, target, reason=None)` - kick user from channel.

`Client.quit(message=pydle.DEFAULT_QUIT_MESSAGE)` - quit network.

`Client.set_nickname(nick)` - attempt to change client nickname.

`Client.message(target, message)` - send a message.

`Client.notice(target, message)` - send a notice.

`Client.set_mode(target, *modes)` - set channel or user modes.

`Client.set_topic(channel, topic)` - set a channel topic.

`Client.away(message)` - set self as away with message.

`Client.back()` - set self as not away anymore.

`Client.whois(nickname)` - retrieve information about user. This method returns a `pydle.async.Future`: calling methods should be wrapped in the `pydle.coroutine` decorator and `yield` the returned future.

`Client.whowas(nickname)` - retrieve information about former user. This method returns a `pydle.async.Future`: see `Client.whois(nickname)` for usage.

with `pydle.features.ctcp`, two extra methods are added:

- `Client.ctcp(target, query)` - send CTCP request;
- `Client.ctcp_reply(target, query, response)` - send CTCP response.

with `pydle.features.cap`, one extra method is added:

- `Client.capability_negotiated(cap, success=True)` - indicate the capability `cap` has been negotiated, where `success` indicates if negotiation succeeded.

with `pydle.features.ircv3_2.monitor`, three methods are added:

- `Client.monitor(nickname)` - add the given nickname to the monitoring list: client will be informed when user gets online or goes offline.
- `Client.unmonitor(nickname)` - remove the given nickname from the monitoring list.
- `Client.is_monitoring(nickname)` - return whether or not the client is monitoring the given nickname.

*Helpers*

`Client.normalize(input)` - normalize input according to currently active connection rules.

`Client.is_channel(target)` - return whether or not `target` is a channel.

`Client.in_channel(channel)` - return whether or not client is in channel.

`Client.is_same_nick(left, right)` - compare nicknames according to proper IRC case mapping.

`Client.is_same_channel(left, right)` - compare channels according to proper IRC case mapping.

*Callbacks*

`Client.on_connect()` - callback called after the client has successfully connected and registered to the server.

`Client.on_disconnect()` - callback called after the client has disconnected from the server.

with `pydle.features.rfc1459`:

`Client.on_quit(user, reason=None)` - callback called when someone (maybe the client) quit the network.

`Client.on_kill(user, source, reason)` - callback called when someone (maybe the client) was killed from the network.

`Client.on_message(target, source, message)` - callback called when the client receives a PRIVMSG, either in a channel or privately.

`Client.on_channel_message(channel, source, message)` - callback called when the client receives a PRIVMSG in a channel.

`Client.on_private_message(source, message)` - callback called when the client receives a private PRIVMSG.

`Client.on_notice(target, source, message)` - callback called when the client receives a NOTICE, either in a channel or privately.

`Client.on_channel_notice(target, source, message)` - callback called when the client receives a NOTICE in a channel.

`Client.on_private_notice(source, message)` - callback called when the client receives a private NOTICE.

`Client.on_invite(channel, source)` - callback called when the client receives an invite to a channel.

`Client.on_join(channel, user)` - callback called when someone (maybe the client) joins a channel.

`Client.on_part(channel, user, message=None)` - callback called when someone (maybe the client) parted a channel.

`Client.on_kick(channel, user, source, reason=None)` - callback called when someone (maybe the client) was kicked from a channel.

`Client.on_topic_change(channel, topic, source)` - callback called when someone sets the topic in a channel.

`Client.on_mode_change(target, modes, source)` - callback called when either someone sets new modes on a channel or the client (or server) change their user mode.

`Client.on_nick_change(old, new)` - callback called when someone (maybe the client) changes their nickname.

`Client.on_unknown(command, source, params)` - callback called when the client receives a raw IRC message it doesn't know how to deal with.

with `pydle.features.ctcp`, two extra callbacks are added, and two generic callbacks:

- `Client.on_ctcp(target, source, query)` - callback called when the client receives a CTCP query, either directed to a channel or to the client privately, that is not handled by `Client.on_ctcp_<query>`;
- `Client.on_ctcp_reply(target, source, query, reply)` - callback called when the client receives a CTCP response, that is not handled by `Client.on_ctcp_<query>_reply`;
- `Client.on_ctcp_<query>(target, source)` - callback called when the client receives a CTCP <query>. The query name should be lower case. Example: `on_ctcp_version(target, source)` will be called if the client receives a CTCP VERSION request;
- `Client.on_ctcp_<query>_reply(target, source, reply)` - callback called when the client receives a CTCP <query> response.

with `pydle.features.isupport`, one generic callback is added:

- `Client.on_isupport_<feature>(value)` - callback called when the server announced support for ISUPPORT feature `feature`. `value` is None if not given by server.

with `pydle.features.cap`, three generic callbacks are added:

- `Client.on_capability_<cap>_available()` - callback called when the server announced support for capability `cap`. Should return whether or not the client wants to request this capability.
- `Client.on_capability_<cap>_enabled()` - callback called when the server acknowledges the client's request for capability `cap`. Should return one of three following values:
  * `pydle.CAPABILITY_NEGOTIATED` - default value assumed when nothing returned. The capability has been successfully negotiated.
  * `pydle.CAPABILITY_NEGOTIATING` - the callback is still negotiating the capability. Stall general capability negotiation until `Client.capability_negotiated(<cap>)` has been called.
  * `pydle.CAPABILITY_FAILED` - the callback failed to negotiate the capability. Attempt to disable it again.
- `Client.on_capability_<cap>_disabled()` - callback called when capability `cap` that was requested before has been disabled.

with `pydle.features.ircv3_2.monitor`, two generic callbacks are added:

- `Client.on_user_online(nickname)` - called when a monitored user got online.
- `Client.on_user_offline(nickname)` - called when a monitored user went offline.

You can also overload `Client.on_raw_<cmd>(message)`, where `cmd` is the raw IRC command (either a text command or a zero-filled numeric code) and `message` an instance of (a subclass of) `protocol.Message` if you really want to, but this is not advisable if you're not building features as it may disable certain built-in functionalities if you're not careful.

**pydle.ClientPool**

`ClientPool(clients)` - instantiate a pool with `clients` as initial clients.

`ClientPool.add(client)` - add client to pool.

`ClientPool.remove(client)` - remove client from pool.

`ClientPool.has_message()` - check whether or not there are unprocessed message(s) available in this pool.

`ClientPool.handle_message()` - handle a single unprocessed message.

`ClientPool.poll_single()` - wait for a new message to arrive.

`ClientPool.poll_forever()` - enter main loop for pool. Will not return until all clients disconnected.

Utilities
---------
`python3 -m pydle.utils.irccat` - simple [irccat](http://sourceforge.net/projects/irccat/)-like implementation built on top of pydle. Read raw IRC commands from stdin, dumps incoming messages to stdout.

`python3 -m pydle.utils.console` - interactive console for a Pydle bot. `self` is defined in-scope as the running bot instance.

`python3 -m pydle.utils.run` - run a Pydle bot in the foreground.

TODO
----
* Work on documentation.
* Finalize IRCv3.2 support.
* Add DCC support.

License
-------
Pydle is licensed under the 3-clause BSD license. See LICENSE.md for details.
