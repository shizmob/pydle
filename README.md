pydle
=====
Python IRC library.
-------------------

pydle is a compact, flexible and standards-abiding IRC library for Python 3.6 through 3.9.

Features
--------
* Well-organized: Thanks to the modularized feature system, it's not hard to find what you're looking for in the well-organised source code.
* Standards-abiding: Based on [RFC1459](https://tools.ietf.org/html/rfc1459.html) with some small extension tweaks, with full support of optional extension standards:
  - [TLS](http://tools.ietf.org/html/rfc5246)
  - [CTCP](http://www.irchelp.org/irchelp/rfc/ctcpspec.html)
  - (coming soon) [DCC](http://www.irchelp.org/irchelp/rfc/dccspec.html) and extensions
  - [ISUPPORT/PROTOCTL](http://tools.ietf.org/html/draft-hardy-irc-isupport-00)
  - [IRCv3.1](http://ircv3.net) (full)
  - [IRCv3.2](http://ircv3.net) (base complete, most optional extensions)
  - [IRCv3.3](http://ircv3.net) (base in progress)
* Asynchronous: IRC is an asynchronous protocol and so should be a library that implements it. Coroutines are used to process events from the server asynchronously.
* Modularised and extensible: Features on top of RFC1459 are implemented as separate modules for a user to pick and choose, and write their own. Broad features are written to be as extensible as possible.
* Liberally licensed: The 3-clause BSD license ensures you can use it everywhere.

Basic Usage
-----------
`pip install pydle`

From there, you can `import pydle` and subclass `pydle.Client` for your own functionality.

> To enable SSL support, install the `sasl` extra.
> `pip install pydle[sasl]`

Setting a nickname and starting a connection over TLS:
```python
import pydle

# Simple echo bot.
class MyOwnBot(pydle.Client):
    async def on_connect(self):
         await self.join('#bottest')

    async def on_message(self, target, source, message):
         # don't respond to our own messages, as this leads to a positive feedback loop
         if source != self.nickname:
            await self.message(target, message)

client = MyOwnBot('MyBot', realname='My Bot')
client.run('irc.rizon.net', tls=True, tls_verify=False)
```

*But wait, I want to handle multiple clients!*

No worries! Use `pydle.ClientPool` like such:
```python
pool = pydle.ClientPool()
for i in range(10):
    client = MyOwnBot('MyBot' + str(i))
    pool.connect(client, 'irc.rizon.net', 6697, tls=True, tls_verify=False)

# This will make sure all clients are treated in a fair way priority-wise.
pool.handle_forever()
```

Furthermore, since pydle is simply `asyncio`-based, you can run the client in your own event loop, like this:
```python
import asyncio

client = MyOwnBot('MyBot')
loop = asyncio.get_event_loop()
asyncio.ensure_future(client.connect('irc.rizon.net', tls=True, tls_verify=False), loop=loop)
loop.run_forever()
```


Customization
-------------

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
    async def on_raw_999(self, source, params):
        """ ACME's custom 999 numeric tells us to change our nickname. """
        nickname = params[0]
        await self.set_nickname(nickname)
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

**Q: How do I...?**

Stop! Read the [documentation](http://pydle.readthedocs.org) first. If you're still in need of support, join us on IRC! We hang at `#pydle` on `irc.libera.chat`. If someone is around, they'll most likely gladly help you.

License
-------

Pydle is licensed under the 3-clause BSD license. See LICENSE.md for details.
