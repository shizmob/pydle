=====================
Introduction to pydle
=====================

What is pydle?
--------------
pydle is an IRC library for Python 3.7 through 3.10.

Although old and dated on some fronts, IRC is still used by a variety of communities as the real-time communication method of choice,
and the most popular IRC networks can still count on tens of thousands of users at any point during the day.

pydle was created out of perceived lack of a good, Pythonic, IRC library solution that also worked with Python 3.
It attempts to follow the standards properly, while also having functionality for the various extensions to the protocol that have been made over the many years.

What isn't pydle?
-----------------
pydle is not an end-user IRC client. Although a simple client may be trivial to implement using pydle, pydle itself does not seek out to be a full-fledged client.
It does, however, provide the building blocks to which you can delegate most, if not all, of your IRC protocol headaches.

pydle also isn't production-ready: while the maintainers try their utmost best to keep the API stable, pydle is still in heavy development,
and APIs are prone to change or removal at least until version 1.0 has been reached.

Requirements
------------
Most of pydle is written in pure, portable Python that only relies on the standard library.
Optionally, if you plan to use pydle's SASL functionality for authentication, the excellent pure-sasl_ library is required.

All dependencies can be installed using the standard package manager for Python, pip, and the included requirements file:

.. code:: bash

  pip install -r requirements.txt

.. _pure-sasl: https://github.com/thobbs/pure-sasl

Compatibility
-------------
pydle works in any interpreter that implements Python 3.7-3.10. Although mainly tested in CPython_, the standard Python implementation,
there is no reason why pydle itself should not work in alternative implementations like PyPy_, as long as they support the Python 3.7 language requirements.

.. _CPython: https://python.org
.. _PyPy: http://pypy.org
