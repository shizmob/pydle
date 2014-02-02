## tags.py
# Tagged message support.
from .. import client
from .. import protocol

TAG_INDICATOR = '@'
TAG_SEPARATOR = ';'
TAG_VALUE_SEPARATOR = '='
TAGGED_MESSAGE_LENGTH_LIMIT = 1024


class TaggedMessage(protocol.Message):
    def __init__(self, command, params, tags=None, **kw):
        if tags is None:
            tags = {}
        super().__init__(command, params, **kw)
        self.tags = tags

    @classmethod
    def parse(cls, line, encoding='utf-8'):
        """
        Parse given line into IRC message structure.
        Returns a TaggedMessage.
        """
        # Decode message.
        try:
            message = line.decode(encoding)
        except UnicodeDecodeError:
            # Try our fallback encoding.
            message = line.decode(protocol.FALLBACK_ENCODING)

        # Sanity check for message length.
        if len(message) > TAGGED_MESSAGE_LENGTH_LIMIT:
            raise protocol.ProtocolViolation('The received message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=TAGGED_MESSAGE_LENGTH_LIMIT), message=message)

        # Strip message separator.
        if message.endswith(protocol.LINE_SEPARATOR):
            message = message[:-len(protocol.LINE_SEPARATOR)]
        elif message.endswith(protocol.MINIMAL_LINE_SEPARATOR):
            message = message[:-len(protocol.MINIMAL_LINE_SEPARATOR)]

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
        return TaggedMessage(message.command, message.params, source=message.source, tags=tags, **message.kw)

    def construct(self):
        """
        Construct raw IRC message and return it.
        """
        message = super().construct()

        # Add tags.
        if self.tags:
            raw_tags = []
            for tag, value in self.tags.items():
                if value == True:
                    raw_tags.append(tag)
                else:
                    raw_tags.append(tag + TAG_VALUE_SEPARATOR + value)

            message = TAG_INDICATOR + TAG_SEPARATOR.join(raw_tags) + ' ' + message

        if len(message) > TAGGED_MESSAGE_LENGTH_LIMIT:
            raise protocol.ProtocolViolation('The constructed message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=TAGGED_MESSAGE_LENGTH_LIMIT), message=message)
        return message


class TaggedMessageSupport(client.BasicClient):
    def _reset_attributes(self):
        super()._reset_attributes()
        self._message_tags_enabled = False

    def _enable_message_tags(self):
        if not self.connected or self._message_tags_enabled:
            return
        self.connection.message = TaggedMessage
        self._message_tags_enabled = True


