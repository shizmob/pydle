===========
Using pydle
===========

.. note::
   This section covers basic use of pydle. To see the full spectrum of what pydle is capable of,
   refer to the :doc:`API reference </api/index>`.

A simple client
---------------
The most basic way to use pydle is instantiating a :class:`pydle.Client` object, connecting it to a server
and having it handle messages forever using :meth:`pydle.Client.handle_forever`.
pydle will automatically take care of ensuring that the connection persists, and will reconnect if for some reason disconnected unexpectedly.

.. code:: python

  import pydle

  client = pydle.Client('MyBot')
  # Client.connect() is a blocking function.
  client.connect('irc.freenode.net', tls=True)
  client.handle_forever()

Adding functionality
--------------------
Of course, the above client doesn't really do much, except idling and error recovery.
To truly start adding functionality to the client, subclass :class:`pydle.Client` and override one or more of the IRC callbacks.

.. code:: python

  import pydle

  class MyClient(pydle.Client):
      """ This is a simple bot that will greet people as they join the channel. """

      def on_connect(self):
          super().on_connect()
          # Can't greet many people without joining a channel.
          self.join('#kochira')

      def on_join(self, channel, user):
          super().on_join(channel, user)
          self.message(channel, 'Hey there, {user}!', user=user)

  client = MyClient('MyBot')
  client.connect('irc.freenode.net', tls=True)
  client.handle_forever()

This trivial example shows a few things:

  1. :meth:`pydle.Client.on_connect` is a callback that gets invoked as soon as the client is fully connected to the server.
  2. :meth:`pydle.Client.on_join` is a callback that gets invoked whenever a user joins a channel.
  3. Trivially enough, we can use :meth:`pydle.Client.join` to instruct the client to join a channel.
  4. Finally, we can use :meth:`pydle.Client.message` to send a message to a channel or to a user;
     it will even format the message for us according to `advanced string formatting`_.

.. hint::
   It is recommended to call the callbacks of the parent class using ``super()``, to make sure whatever functionality
   implemented by your parent classes gets called too: pydle will gracefully handle the call even if no functionality
   was implemented or no callbacks overridden.

.. _`advanced string formatting`: http://legacy.python.org/dev/peps/pep-3101/

Multiple servers, multiple clients
----------------------------------
Any pydle client instance can only be connected to a single server. That doesn't mean that you are restricted
to only being active on a single server at once, though. Using a :class:`pydle.ClientPool`,
you can instantiate multiple clients, connect them to different servers using :meth:`pydle.ClientPool.connect`,
and handle them within a single loop.

.. code:: python

  import pydle

  class MyClient(pydle.Client):
      """ This is a simple bot that will greet people as they join the channel. """

      def on_connect(self):
          super().on_connect()
          # Can't greet many people without joining a channel.
          self.join('#kochira')

      def on_join(self, channel, user):
          super().on_join(channel, user)
          self.message(channel, 'Hey there, {user}!', user=user)

  # Setup pool and connect clients.
  pool = pydle.ClientPool()
  servers = [ 'irc.freenode.net', 'irc.rizon.net', 'irc.esper.net' ]

  for server in servers:
      client = MyClient('MyBot')
      pool.connect(client, server, tls=True)

  # Handle all clients in the pool at once.
  pool.handle_forever()

.. warning::
   While multiple :class:`pydle.ClientPool` instances can be created and ran, you should ensure a client is only
   active in a single :class:`pydle.ClientPool` at once. Being active in multiple pools can lead to strange things
   like receiving messages twice, or interleaved outgoing messages.

Mixing and matching
-------------------
Thanks to pydle's modular "feature" system, you don't have to support everything you want to support.
You can choose just to select the options you think you need for your client by using :func:`pydle.featurize` to create a base class
out of the featured you need.

.. code:: python

   import pydle

   # Create a client that just supports the base RFC1459 spec, CTCP and an IRC services-style account system.
   MyBaseClient = pydle.featurize(pydle.features.RFC1459Support, pydle.features.CTCPSupport, pydle.features.AccountSupport)

   class MyClient(MyBaseClient):
       ...


A list of all available built-in features and their use can be found at the :doc:`API reference </api/features>`.

In addition to this, you can of course also write your own features. Feature writing is discussed thoroughly in the :doc:`feature section </features/index>`.
Once you have written a feature, you can just featurize it on top of an existing client class.

.. code:: python

   import pydle
   import vendor

   # Add vendor feature on top of the base client.
   MyBaseClient = pydle.featurize(pydle.Client, vendor.VendorExtensionSupport)

   class MyClient(MyBaseClient):
       ...

Asynchronous functionality
--------------------------
Some actions inevitably require blocking and waiting for a result. Since pydle is an asynchronous library where a client runs in a single thread,
doing this blindly could lead to issues like the operation blocking the handling of messages entirely.

Fortunately, pydle implements coroutines_ which allow you to handle a blocking operation almost as if it were a regular operation,
while still retaining the benefits of asynchronous program flow. Coroutines allow pydle to be notified when a blocking operation is done,
and then resume execution of the calling function appropriately. That way, blocking operations do not block the entire program flow,

In order for a function to be declared as a coroutine, it has to be decorated using the :func:`pydle.coroutine` decorator.
It can then call functions that would normally block using Python's ``yield`` operator.
Since a function that calls a blocking function is itself blocking too, it has to be declared a coroutine as well.

.. hint::
   As with a lot of things, documentation is key.
   Documenting that your function does blocking operations lets the caller know how to call the function,
   and to include the fact that it calls blocking operations in its own documentation for its own callers.

For example, if you are implementing an administrative system that works based off nicknames, you might want to check
if the users are identified to ``NickServ``. However, WHOISing a user using :meth:`pydle.Client.whois` would be a blocking operation.
Thanks to coroutines and :meth:`pydle.Client.whois` being a blocking operation compatible with coroutines,
the act of WHOISing will not block the entire program flow of the client.

.. code:: python

  import pydle
  ADMIN_NICKNAMES = [ 'Shiz', 'rfw' ]

  class MyClient(pydle.Client):
      """
      This is a simple bot that will tell you if you're an administrator or not.
      A real bot with administrative-like capabilities would probably be better off maintaining a cache
      that would be invalidated upon parting, quitting or changing nicknames.
      """

      def on_connect(self):
          super().on_connect()
          self.join('#kochira')

      @pydle.coroutine
      def is_admin(self, nickname):
          """
          Check whether or not a user has administrative rights for this bot.
          This is a blocking function: use a coroutine to call it.
          See pydle's documentation on blocking functionality for details.
          """
          admin = False

          # Check the WHOIS info to see if the source has identified with NickServ.
          # This is a blocking operation, so use yield.
          if source in ADMIN_NICKNAMES:
              info = yield self.whois(source)
              admin = info['identified']

          return admin

      @pydle.coroutine
      def on_message(self, target, source, message):
          super().on_message(target, source, message)

          # Tell a user if they are an administrator for this bot.
          if message.startswith('!adminstatus'):
              admin = yield self.is_admin(source)

              if admin:
                  self.message(target, '{source}: You are an administrator.', source=source)
              else:
                  self.message(target, '{source}: You are not an administrator.', source=source)

Writing your own blocking operation that can work with coroutines is trivial:
just make your blocking method return a :class:`pydle.Future` instance (without the act of creating and returning the Future itself being blocking),
and any coroutine yielding it will halt execution until the returned future is resolved, using either
:meth:`pydle.Future.set_result` or :meth:`pydle.Future.set_exception`, while pydle can still handle everything else.

.. _coroutines: https://en.wikipedia.org/wiki/Coroutine
