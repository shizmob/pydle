==========
Client API
==========
.. module:: pydle.client


.. class:: pydle.Client

   :class:`pydle.Client` implements the featureset of :class:`pydle.BasicClient` with all the features in the :mod:`pydle.features` namespace added.
   For the full reference, check the :class:`pydle.BasicClient` documentation and the :doc:`Feature API reference </api/features>`.

.. class:: pydle.MinimalClient

   :class:`pydle.MinimalClient` implements the featureset of :class:`pydle.BasicClient` with some vital features in the :mod:`pydle.features` namespace added, namely:

     * :class:`pydle.features.RFC1459Support`
     * :class:`pydle.features.TLSSupport`
     * :class:`pydle.features.CTCPSupport`
     * :class:`pydle.features.ISUPPORTSupport`
     * :class:`pydle.features.WHOXSupport`

   For the full reference, check the :class:`pydle.BasicClient` documentation and the :doc:`Feature API reference </api/features>`.

-----

.. autoclass:: pydle.ClientPool
   :members:

-----

.. autofunction:: pydle.featurize

.. autoclass:: pydle.BasicClient
   :members:

   :attr:`users`

     A :class:`dict` mapping a username to a :class:`dict` with general information about that user.
     Available keys in the information dict:

       * ``nickname``: The user's nickname.
       * ``username``: The user's reported username on their source device.
       * ``realname``: The user's reported real name (GECOS).
       * ``hostname``: The hostname where the user is connecting from.

   :attr:`channels`

     A :class:`dict` mapping a joined channel name to a :class:`dict` with information about that channel.
     Available keys in the information dict:

      * ``users``: A :class:`set` of all users currently in the channel.
