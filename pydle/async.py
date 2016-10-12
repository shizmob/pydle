## async.py
# Light wrapper around whatever async library pydle uses.
import os
import functools
import itertools
import collections
import threading
import datetime
import types

import asyncio

FUTURE_TIMEOUT = 30


class Future(asyncio.Future):
    """
    A future. An object that represents a result that has yet to be created or returned.
    """

def coroutine(f):
    return asyncio.coroutine(f)

def parallel(*futures):
    return asyncio.gather(*futures)


class EventLoop:
    """ A light wrapper around what event loop mechanism pydle uses underneath. """

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or asyncio.get_event_loop()
        self.handlers = {}
        self.handling = {}
        self.future_timeout = FUTURE_TIMEOUT
        self.event_types = {
            'read':  (self.io_loop.add_reader, self.io_loop.remove_reader),
            'write': (self.io_loop.add_writer, self.io_loop.remove_writer)
        }
        self._future_timeouts = {}
        self._timeout_id = 0
        self._timeout_handles = {}

    def __del__(self):
        self.io_loop.close()


    @property
    def running(self):
        return self.io_loop.is_running()


    def register(self, fd):
        """ Register a file descriptor with this event loop. """
        self.handlers[fd] = {e: [] for e in self.event_types}
        self.handling[fd] = {e: False for e in self.event_types}

    def unregister(self, fd):
        """ Unregister a file descriptor with this event loop. """
        del self.handlers[fd]
        del self.handling[fd]


    def on_read(self, fd, callback):
        """
        Add a callback for when the given file descriptor is available for reading.
        Callback will be called with file descriptor as sole argument.
        """
        self.handlers[fd]['read'].append(callback)
        self._update_events(fd)

    def on_write(self, fd, callback):
        """
        Add a callback for when the given file descriptor is available for writing.
        Callback will be called with file descriptor as sole argument.
        """
        self.handlers[fd]['write'].append(callback)
        self._update_events(fd)

    def off_read(self, fd, callback):
        """ Remove read callback for given file descriptor. """
        self.handlers[fd]['read'].remove(callback)
        self._update_events(fd)

    def off_write(self, fd, callback):
        """ Remove write callback for given file descriptor. """
        self.handlers[fd]['write'].remove(callback)
        self._update_events(fd)

    def handles_read(self, fd, callback):
        """ Return whether or the given read callback is active for the given file descriptor. """
        return callback in self.handlers[fd]['read']

    def handles_write(self, fd, callback):
        """ Return whether or the given write callback is active for the given file descriptor. """
        return callback in self.handlers[fd]['write']


    def _update_events(self, fd):
        for e, (adder, remover) in self.event_types.items():
            if self.handlers[fd][e] and not self.handling[fd][e]:
                adder(fd, self._do_on_event, fd, e)
                self.handling[fd][e] = True
            elif not self.handlers[fd][e] and self.handling[fd][e]:
                remover(fd)
                self.handling[fd][e] = False

    def _do_on_event(self, fd, event):
        if fd not in self.handlers:
            return

        for handler in self.handlers[fd][event]:
            handler(fd)


    def on_future(self, _future, _callback, *_args, **_kwargs):
        """ Add a callback for when the given future has been resolved. """
        callback = functools.partial(self._do_on_future, _callback, _args, _kwargs)

        # Create timeout handler and regular handler.
        self._future_timeouts[_future] = self.schedule_in(self.future_timeout, callback)
        future.add_done_callback(callback)

    def _do_on_future(self, callback, args, kwargs, future):
        # This was a time-out.
        if not future.done():
            future.set_exception(TimeoutError('Future timed out before yielding a result.'))
            del self._future_timeouts[future]
        # This was a time-out that already has been handled.
        elif isinstance(future.exception(), TimeoutError):
            return
        # A regular result. Cancel the timeout.
        else:
            self.unschedule(self._future_timeouts.pop(future))

        # Call callback.
        callback(*args, **kwargs)


    def _get_schedule_handle(self):
        """ Get a unique handle for use in the schedule_* functions. """
        # Just use a simple monotonically increasing number.
        handle = self._timeout_id
        self._timeout_id += 1

        return handle

    def schedule(self, _callback, *_args, **_kwargs):
        """ Schedule a callback to be ran as soon as possible in this loop. """
        self.io_loop.call_soon_threadsafe(_callback, *_args, **_kwargs)

    def schedule_in(self, _when, _callback, *_args, **_kwargs):
        """
        Schedule a callback to be ran as soon as possible after `when` seconds have passed.
        Will return an opaque handle that can be passed to `unschedule` to unschedule the function.
        """
        if isinstance(_when, datetime.timedelta):
            _when = _when.total_seconds()

        # Create ID for this timeout.
        id = self._get_schedule_handle()
        self._timeout_handles[id] = self.io_loop.call_later(_when, functools.partial(_callback, *_args, **_kwargs))

        return id

    def schedule_periodically(self, _interval, _callback, *_args, **_kwargs):
        """
        Schedule a callback to be ran every `interval` seconds.
        Will return an opaque handle that can be passed to unschedule() to unschedule the interval function.
        A function will also stop being scheduled if it returns False or raises an Exception.
        """
        if isinstance(_interval, datetime.timedelta):
            _interval = _interval.total_seconds()

        # Create ID for this periodic.
        id = self._get_schedule_handle()
        self._timeout_handles[id] = self.io_loop.call_later(interval, functools.partial(self._periodic_handler, id, interval, callback, args, kwargs))

        return id

    def _periodic_handler(self, id, interval, callback, args, kwargs):
        # We could've been unscheduled for some reason.
        if not self.is_scheduled(id):
            return

        # Call callback, and schedule again if it doesn't return False.
        self._timeout_handles[id] = self.io_loop.call_later(interval, functools.partial(self._periodic_handler, id, interval, callback, args, kwargs))
        result = False

        try:
            result = callback(*args, **kwargs)
        finally:
            if result == False:
                self.unschedule(id)

    def is_scheduled(self, handle):
        """ Return whether or not the given handle is still scheduled. """
        return handle in self._timeout_handles

    def unschedule(self, handle):
        """ Unschedule a given timeout or periodical callback. """
        if self.is_scheduled(handle):
            handle = self._timeout_handles.pop(handle)
            handle.cancel()


    def run(self):
        """ Run the event loop. """
        if not self.running:
            self.io_loop.run_forever()

    def run_with(self, func):
        """ Run loop, call function, stop loop. If function returns a future, run until the future has been resolved. """
        return self.run_until(asyncio.ensure_future(func))

    def run_until(self, future):
        """ Run until future is resolved. """
        self.io_loop.run_until_complete(future)

    def stop(self):
        """ Stop the event loop. """
        if self.running:
            self.io_loop.stop()
