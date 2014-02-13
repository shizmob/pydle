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
    def __init__(self, command, params, tags=None, **kw):
        if tags is None:
            tags = {}
        super().__init__(command, params, **kw)
        self.tags = tags

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
        if message.endswith(pydle.protocol.LINE_SEPARATOR):
            message = message[:-len(pydle.protocol.LINE_SEPARATOR)]
        elif message.endswith(pydle.protocol.MINIMAL_LINE_SEPARATOR):
            message = message[:-len(pydle.protocol.MINIMAL_LINE_SEPARATOR)]

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
        return TaggedMessage(message.command, message.params, _valid=message._valid and valid, source=message.source, tags=tags, **message.kw)

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
    def _reset_attributes(self):
        super()._reset_attributes()
        self._message_tags_enabled = False

    def _enable_message_tags(self):
        self._message_tags_enabled = True

    def _parse_message(self):
        if self._message_tags_enabled:
            sep = rfc1459.parsing.MINIMAL_LINE_SEPARATOR.encode(self.connection.encoding)
            message, _, data = self._receive_buffer.partition(sep)
            self._receive_buffer = data

            return TaggedMessage.parse(message, encoding=self.connection.encoding)
        else:
            return super()._parse_message()
