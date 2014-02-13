## async.py
# Light wrapper around whatever async library pydle uses.
import functools
import tornado.concurrent
import tornado.ioloop


class EventLoop:
    """ A light wrapper around what event loop mechanism pydle uses underneath. """
    EVENT_MAPPING = {
        'read': tornado.ioloop.IOLoop.READ,
        'write': tornado.ioloop.IOLoop.WRITE,
        'error': tornado.ioloop.IOLoop.ERROR
    }

    def __init__(self, io_loop=None):
        if io_loop is None:
            io_loop = tornado.ioloop.IOLoop.current()
        self.io_loop = io_loop
        self.running = False
        self.handlers = {}
        self._context_future = None

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
        self.io_loop.remove_handler(fd)

        events = 0
        for event, ident in self.EVENT_MAPPING.items():
            if self.handlers[fd][event]:
                events |= ident
        self.io_loop.add_handler(fd, self._do_on_event, events)

    def _do_on_event(self, fd, events):
        if fd not in self.handlers:
            return

        for event, ident in self.EVENT_MAPPING.items():
            if events & ident:
                for handler in self.handlers[fd][event]:
                    handler(fd)


    def on_future(_self, _future, _callback, *_args, **_kwargs):
        """ Add a callback for when the given future has been resolved. """
        _self.io_loop.add_future(_future, functools.partial(_self._do_on_future, _callback, _args, _kwargs))

    def _do_on_future(self, callback, args, kwargs):
        return callback(*args, **kwargs)


    def schedule(_self, _callback, *_args, **_kwargs):
        """ Schedule a callback to be ran as soon as possible in this loop. """
        _self.io_loop.add_callback(_callback, *_args, **_kwargs)

    def schedule_in(_self, _when, _callback, *_args, **_kwargs):
        """ Schedule a callback to be ran as soon as possible after `when` seconds have passed. """
        # Schedule scheduling in IOLoop thread because of thread-safety.
        _self.schedule(functools.partial(_self._do_schedule_in, _when, _callback, _args, _kwargs))

    def schedule_periodically(_self, _interval, _callback, *_args, **_kwargs):
        """ Schedule a callback to be ran every `interval` seconds. """
        # Schedule scheduling in IOLoop thread because of thread-safety.
        _self.schedule(functools.partial(_self._do_schedule_periodically, _interval, _callback, _args, _kwargs))

    def _do_schedule_in(self, when, callback, args, kwargs):
        return self.io_loop.add_timeout(when, functools.partial(callback, *args, **kwargs))

    def _do_schedule_periodically(self, interval, callback, args, kwargs):
        # Use a wrapper function
        return self.io_loop.add_timeout(interval, functools.partial(self._periodical_handler, interval, callback, args, kwargs))

    def _periodical_handler(self, interval, callback, args, kwargs):
        # Call callback, and schedule again if it doesn't return False.
        handle = self._do_schedule_in(interval, callback, args, kwargs)
        if callback(*args, **kwargs) == False:
            self.io_loop.remove_timeout(handle)



    def run(self):
        """ Run the event loop. """
        if not self.running:
            self.io_loop.start()
            self.running = True

    def stop(self):
        """ Stop the event loop. """
        if self.running:
            self.io_loop.stop()
            self.running = False


    def __enter__(self):
        if not self.running:
            self.io_loop.run_sync(self._create_context_future)
            self.running = True

    def __exit__(self):
        if self.running:
            if self._context_future:
                self._resolve_context_future()
            self.running = False

    def _create_context_future(self):
        # Resolve any existing future first.
        if self._context_future:
            self._resolve_context_future()

        self._context_future = tornado.concurrent.Future()
        return self._context_future

    def _resolve_context_future(self):
        self._context_future.set_result(True)
        self._context_future = None
