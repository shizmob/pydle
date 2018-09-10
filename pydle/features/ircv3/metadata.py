from pydle import async
from . import cap

VISIBLITY_ALL = '*'


class MetadataSupport(cap.CapabilityNegotiationSupport):

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()

        self._pending['metadata'] = {}
        self._metadata_info = {}
        self._metadata_queue = []

    ## IRC API.

    @async.coroutine
    def get_metadata(self, target):
        """
        Return user metadata information.
        This is a blocking asynchronous method: it has to be called from a coroutine, as follows:

            metadata = yield from self.get_metadata('#foo')
        """
        if target not in self._pending['metadata']:
            yield from self.rawmsg('METADATA', target, 'LIST')

            self._metadata_queue.append(target)
            self._metadata_info[target] = {}
            self._pending['metadata'][target] = self.eventloop.create_future()

        return self._pending['metadata'][target]

    @async.coroutine
    def set_metadata(self, target, key, value):
        yield from self.rawmsg('METADATA', target, 'SET', key, value)

    @async.coroutine
    def unset_metadata(self, target, key):
        yield from self.rawmsg('METADATA', target, 'SET', key)

    @async.coroutine
    def clear_metadata(self, target):
        yield from self.rawmsg('METADATA', target, 'CLEAR')


    ## Callbacks.

    @async.coroutine
    def on_metadata(self, target, key, value, visibility=None):
        pass


    ## Message handlers.

    @async.coroutine
    def on_capability_metadata_notify_available(self, value):
        return True

    @async.coroutine
    def on_raw_metadata(self, message):
        """ Metadata event. """
        target, targetmeta = self._parse_user(message.params[0])
        key, visibility, value = message.params[1:4]
        if visibility == VISIBLITY_ALL:
            visibility = None

        if target in self.users:
            self._sync_user(target, targetmeta)
        yield from self.on_metadata(target, key, value, visibility=visibility)

    @async.coroutine
    def on_raw_760(self, message):
        """ Metadata key/value for whois. """
        target, targetmeta = self._parse_user(message.params[0])
        key, _, value = message.params[1:4]

        if target not in self._pending['whois']:
            return
        if target in self.users:
            self._sync_user(target, targetmeta)

        self._whois_info[target].setdefault('metadata', {})
        self._whois_info[target]['metadata'][key] = value

    @async.coroutine
    def on_raw_761(self, message):
        """ Metadata key/value. """
        target, targetmeta = self._parse_user(message.params[0])
        key, visibility = message.params[1:3]
        value = message.params[3] if len(message.params) > 3 else None

        if target not in self._pending['metadata']:
            return
        if target in self.users:
            self._sync_user(target, targetmeta)

        self._metadata_info[target][key] = value

    @async.coroutine
    def on_raw_762(self, message):
        """ End of metadata. """
        # No way to figure out whose query this belongs to, so make a best guess
        # it was the first one.
        if not self._metadata_queue:
            return
        nickname = self._metadata_queue.pop()

        future = self._pending['metadata'].pop(nickname)
        future.set_result(self._metadata_info.pop(nickname))

    @async.coroutine
    def on_raw_764(self, message):
        """ Metadata limit reached. """
        pass

    @async.coroutine
    def on_raw_765(self, message):
        """ Invalid metadata target. """
        target, targetmeta = self._parse_user(message.params[0])

        if target not in self._pending['metadata']:
            return
        if target in self.users:
            self._sync_user(target, targetmeta)

        self._metadata_queue.remove(target)
        del self._metadata_info[target]

        future = self._pending['metadata'].pop(target)
        future.set_result(None)

    @async.coroutine
    def on_raw_766(self, message):
        """ Unknown metadata key. """
        pass

    @async.coroutine
    def on_raw_767(self, message):
        """ Invalid metadata key. """
        pass

    @async.coroutine
    def on_raw_768(self, message):
        """ Metadata key not set. """
        pass

    @async.coroutine
    def on_raw_769(self, message):
        """ Metadata permission denied. """
        pass
