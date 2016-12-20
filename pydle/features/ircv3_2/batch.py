## batch.py
# Batch process support.
from . import tags

NEW_SIGIL = '+'
END_SIGIL = '-'


class BatchProcessingSupport(tags.MessageTaggingSupport):
    """ Support for batch processing of messages. """

    ## Internals.

    def _reset_attributes(self):
        super()._reset_attributes()
        self._batches = {}

    def _handle_message(self, message):
        """ Queue up message if we're in the middle of handling a batch. """
        if 'batch' in self._capabilities and 'batch' in message.tags and message.tags['batch'] in self._batches:
            # Queue up message for later handling.
            self._batches[message.tags['batch']].append(message)
        else:
            super()._handle_message(message)

    ## Callbacks.

    def on_capability_batch_available(self):
        self._enable_message_tags()
        return True

    def on_batch(self, messages):
        """ Handle batch of messages. Return true if the batch was processed and doesn't require further messages. """
        pass

    def on_raw_batch(self, message):
        """ Message indicating batch start/end. """
        if message.params[0].startswith(NEW_SIGIL):
            # Register batch.
            id = message.params[0].[len(NEW_SIGIL):]
            length = message.params[1]
            self._batches[id] = []
        elif message.params[0].startswith(END_SIGIL):
            # Batch ended, process it.
            id = message.params[0].[len(END_SIGIL):]
            batch = self._batches[id]
            del self._batches[id]

            # All the same commands? If so, we can try to invoke a special handler.
            samey = len(set(message.command for message in batch)) == 1
            specific_handler = 'on_batch_' + batch[0].command.lower() if batch else ''

            processed = False
            if samey and hasattr(self, specific_handler):
                # Most specific handler.
                processed = getattr(self, specific_handler)(batch)
            if not processed:
                # General handler.
                processed = self.on_batch(batch)
            if not processed:
                # Process all messages ourselves.
                for message in batch:
                    self._handle_message(message)
