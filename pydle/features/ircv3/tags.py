## tags.py
# Tagged message support.
import pydle.client
import pydle.protocol
from pydle.features import rfc1459

TAG_INDICATOR = '@'
TAG_SEPARATOR = ';'
TAG_VALUE_SEPARATOR = '='
TAGGED_MESSAGE_LENGTH_LIMIT = 1024


class TaggedMessage(rfc1459.RFC1459Message):
    def __init__(self, tags=None, **kw):
        super().__init__(**kw)
        self._kw['tags'] = tags
        self.__dict__.update(self._kw)

    @classmethod
    def parse(cls, line, encoding=pydle.protocol.DEFAULT_ENCODING):
        """
        Parse given line into IRC message structure.
        Returns a TaggedMessage.
        """
        valid = True
        # Decode message.
        try:
            message = line.decode(encoding)
        except UnicodeDecodeError:
            # Try our fallback encoding.
            message = line.decode(pydle.protocol.FALLBACK_ENCODING)

        # Sanity check for message length.
        if len(message) > TAGGED_MESSAGE_LENGTH_LIMIT:
            valid = False

        # Strip message separator.
        if message.endswith(rfc1459.protocol.LINE_SEPARATOR):
            message = message[:-len(rfc1459.protocol.LINE_SEPARATOR)]
        elif message.endswith(rfc1459.protocol.MINIMAL_LINE_SEPARATOR):
            message = message[:-len(rfc1459.protocol.MINIMAL_LINE_SEPARATOR)]
        raw = message

        # Parse tags.
        tags = {}
        if message.startswith(TAG_INDICATOR):
            message = message[len(TAG_INDICATOR):]
            raw_tags, message = message.split(' ', 1)

            for raw_tag in raw_tags.split(TAG_SEPARATOR):
                if TAG_VALUE_SEPARATOR in raw_tag:
                    tag, value = raw_tag.split(TAG_VALUE_SEPARATOR, 1)
                else:
                    tag = raw_tag
                    value = True
                tags[tag] = value

        # Parse rest of message.
        message = super().parse(message.lstrip().encode(encoding), encoding=encoding)
        return TaggedMessage(_raw=raw, _valid=message._valid and valid, tags=tags, **message._kw)

    def construct(self, force=False):
        """
        Construct raw IRC message and return it.
        """
        message = super().construct(force=force)

        # Add tags.
        if self.tags:
            raw_tags = []
            for tag, value in self.tags.items():
                if value == True:
                    raw_tags.append(tag)
                else:
                    raw_tags.append(tag + TAG_VALUE_SEPARATOR + value)

            message = TAG_INDICATOR + TAG_SEPARATOR.join(raw_tags) + ' ' + message

        if len(message) > TAGGED_MESSAGE_LENGTH_LIMIT and not force:
            raise protocol.ProtocolViolation('The constructed message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=TAGGED_MESSAGE_LENGTH_LIMIT), message=message)
        return message


class TaggedMessageSupport(rfc1459.RFC1459Support):
    def _create_message(self, command, *params, tags={}, **kwargs):
        message = super()._create_message(command, *params, **kwargs)
        return TaggedMessage(tags=tags, **message._kw)

    def _parse_message(self):
        sep = rfc1459.protocol.MINIMAL_LINE_SEPARATOR.encode(self.encoding)
        message, _, data = self._receive_buffer.partition(sep)
        self._receive_buffer = data

        return TaggedMessage.parse(message + sep, encoding=self.encoding)

