## async.py
# Light wrapper around whatever async library pydle uses.
import os
import functools
import itertools
import collections
import threading
import datetime
import types

import tornado.concurrent
import tornado.ioloop

FUTURE_TIMEOUT = 30


class Future(tornado.concurrent.TracebackFuture):
    """
    A future. An object that represents a result that has yet to be created or returned.
    """


def coroutine(func):
    """ Decorator for coroutine functions that need to block for asynchronous operations. """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return_future = Future()

        def handle_future(future):
            # Chained futures!
            try:
                if future.exception() is not None:
                    result = gen.throw(future.exception())
                else:
                    result = gen.send(future.result())
                if isinstance(result, tuple):
                    result = parallel(*result)
                result.add_done_callback(handle_future)
            except StopIteration as e:
                return_future.set_result(getattr(e, 'value', None))
            except Exception as e:
                return_future.set_exception(e)

        try:
            # Handle initial value.
            gen = func(*args, **kwargs)
        except Exception as e:
            return_future.set_exception(e)
            return return_future
        else:
            # If this isn't a generator, then wrap the result with a future.
            if not isinstance(gen, types.GeneratorType):
                return_future.set_result(gen)
                return return_future

        try:
            result = next(gen)
            if isinstance(result, tuple):
                result = parallel(*result)
            result.add_done_callback(handle_future)
        except StopIteration as e:
            return_future.set_result(getattr(e, 'value', None))
        except Exception as e:
            return_future.set_exception(e)

        return return_future
    return wrapper

def parallel(*futures):
    """ Create a single future that will be completed when all the given futures are. """
    result_future = Future()
    results = collections.OrderedDict(zip(futures, itertools.repeat(None)))
    futures = list(futures)

    if not futures:
        # If we don't have any futures, then we return an empty tuple.
        result_future.set_result(())
        return result_future

    def done(future):
        futures.remove(future)
        results[future] = future.result()
        # All out of futures. set the result.
        if not futures:
            result_future.set_result(tuple(results.values()))

    for future in futures:
        future.add_done_callback(done)

    return result_future


class EventLoop:
    """ A light wrapper around what event loop mechanism pydle uses underneath. """
    EVENT_MAPPING = {
        'read': tornado.ioloop.IOLoop.READ,
        'write': tornado.ioloop.IOLoop.WRITE,
        'error': tornado.ioloop.IOLoop.ERROR
    }

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        self.running = False
        self.run_thread = None
        self.handlers = {}
        self.future_timeout = FUTURE_TIMEOUT
        self._registered_events = set()
        self._future_timeouts = {}
        self._timeout_id = 0
        self._timeout_handles = {}

    def __del__(self):
        self.io_loop.close()


    def register(self, fd):
        """ Register a file descriptor with this event loop. """
        self.handlers[fd] = { key: [] for key in self.EVENT_MAPPING }

    def unregister(self, fd):
        """ Unregister a file descriptor with this event loop. """
        del self.handlers[fd]


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

    def on_error(self, fd, callback):
        """
        Add a callback for when an error has occurred on the given file descriptor.
        Callback will be called with file descriptor as sole argument.
        """
        self.handlers[fd]['error'].append(callback)
        self._update_events(fd)

    def off_read(self, fd, callback):
        """ Remove read callback for given file descriptor. """
        self.handlers[fd]['read'].remove(callback)
        self._update_events(fd)

    def off_write(self, fd, callback):
        """ Remove write callback for given file descriptor. """
        self.handlers[fd]['write'].remove(callback)
        self._update_events(fd)

    def off_error(self, fd, callback):
        """ Remove error callback for given file descriptor. """
        self.handlers[fd]['error'].remove(callback)
        self._update_events(fd)

    def handles_read(self, fd, callback):
        """ Return whether or the given read callback is active for the given file descriptor. """
        return callback in self.handlers[fd]['read']

    def handles_write(self, fd, callback):
        """ Return whether or the given write callback is active for the given file descriptor. """
        return callback in self.handlers[fd]['write']

    def handles_error(self, fd, callback):
        """ Return whether or the given error callback is active for the given file descriptor. """
        return callback in self.handlers[fd]['error']


    def _update_events(self, fd):
        if fd in self._registered_events:
            self.io_loop.remove_handler(fd)

        events = 0
        for event, ident in self.EVENT_MAPPING.items():
            if self.handlers[fd][event]:
                events |= ident

        self.io_loop.add_handler(fd, self._do_on_event, events)
        self._registered_events.add(fd)

    def _do_on_event(self, fd, events):
        if fd not in self.handlers:
            return

        for event, ident in self.EVENT_MAPPING.items():
            if events & ident:
                for handler in self.handlers[fd][event]:
                    handler(fd)


    def on_future(self, _future, _callback, *_args, **_kwargs):
        """ Add a callback for when the given future has been resolved. """
        callback = functools.partial(self._do_on_future, _callback, _args, _kwargs)

        # Create timeout handler and regular handler.
        self._future_timeouts[_future] = self.schedule_in(self.future_timeout, callback)
        self.io_loop.add_future(_future, callback)

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
        self.io_loop.add_callback(_callback, *_args, **_kwargs)

    def schedule_in(self, _when, _callback, *_args, **_kwargs):
        """
        Schedule a callback to be ran as soon as possible after `when` seconds have passed.
        Will return an opaque handle that can be passed to `unschedule` to unschedule the function.
        """
        if not isinstance(_when, datetime.timedelta):
            _when = datetime.timedelta(seconds=_when)

        # Create ID for this timeout.
        id = self._get_schedule_handle()

        if self.run_thread != threading.current_thread().ident:
            # Schedule scheduling in IOLoop thread because of thread-safety.
            self.schedule(functools.partial(self._do_schedule_in, id, _when, _callback, _args, _kwargs))
        else:
            self._do_schedule_in(id, _when, _callback, _args, _kwargs)

        return id

    def schedule_periodically(self, _interval, _callback, *_args, **_kwargs):
        """
        Schedule a callback to be ran every `interval` seconds.
        Will return an opaque handle that can be passed to unschedule() to unschedule the interval function.
        A function will also stop being scheduled if it returns False or raises an Exception.
        """
        if not isinstance(_interval, datetime.timedelta):
            _interval = datetime.timedelta(seconds=_interval)

        # Create ID for this periodic.
        id = self._get_schedule_handle()

        if self.run_thread != threading.current_thread().ident:
            # Schedule scheduling in IOLoop thread because of thread-safety.
            self.schedule(functools.partial(self._do_schedule_periodically, id, _interval, _callback, _args, _kwargs))
        else:
            self._do_schedule_periodically(id, _interval, _callback, _args, _kwargs)

        return id

    def _do_schedule_in(self, id, when, callback, args, kwargs):
        self._timeout_handles[id] = self.io_loop.add_timeout(when, functools.partial(callback, *args, **kwargs))

    def _do_schedule_periodically(self, id, interval, callback, args, kwargs):
        # Use a wrapper function.
        self._timeout_handles[id] = self.io_loop.add_timeout(interval, functools.partial(self._periodic_handler, id, interval, callback, args, kwargs))

    def _periodic_handler(self, id, interval, callback, args, kwargs):
        # We could've been unscheduled for some reason.
        if not self.is_scheduled(id):
            return

        # Call callback, and schedule again if it doesn't return False.
        self._do_schedule_periodically(id, interval, callback, args, kwargs)
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
            self.io_loop.remove_timeout(handle)


    def run(self):
        """ Run the event loop. """
        if not self.running:
            self.running = True
            self.run_thread = threading.current_thread().ident
            self.io_loop.start()
            self.run_thread = None
            self.running = False

    def run_with(self, func):
        """ Run loop, call function, stop loop. If function returns a future, run until the future has been resolved. """
        self.running = True
        self.run_thread = threading.current_thread().ident
        self.io_loop.run_sync(func)
        self.run_thread = None
        self.running = False

    def run_until(self, future):
        """ Run until future is resolved. """
        return self.run_with(lambda: future)

    def stop(self):
        """ Stop the event loop. """
        if self.running:
            self.io_loop.stop()
