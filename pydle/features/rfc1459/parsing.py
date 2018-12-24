## parsing.py
# RFC1459 parsing and construction.
import collections.abc
import pydle.protocol
from . import protocol

class RFC1459Message(pydle.protocol.Message):
    def __init__(self, command, params, source=None, _raw=None, _valid=True, **kw):
        self._kw = kw
        self._kw['command'] = command
        self._kw['params'] = params
        self._kw['source'] = source
        self._valid = _valid
        self._raw = _raw
        self.__dict__.update(self._kw)

    @classmethod
    def parse(cls, line, encoding=pydle.protocol.DEFAULT_ENCODING):
        """
        Parse given line into IRC message structure.
        Returns a Message.
        """
        valid = True

        # Decode message.
        try:
            message = line.decode(encoding)
        except UnicodeDecodeError:
            # Try our fallback encoding.
            message = line.decode(pydle.protocol.FALLBACK_ENCODING)

        # Sanity check for message length.
        if len(message) > protocol.MESSAGE_LENGTH_LIMIT:
            valid = False

        # Strip message separator.
        if message.endswith(protocol.LINE_SEPARATOR):
            message = message[:-len(protocol.LINE_SEPARATOR)]
        elif message.endswith(protocol.MINIMAL_LINE_SEPARATOR):
            message = message[:-len(protocol.MINIMAL_LINE_SEPARATOR)]

        # Sanity check for forbidden characters.
        if any(ch in message for ch in protocol.FORBIDDEN_CHARACTERS):
            valid = False

        # Extract message sections.
        # Format: (:source)? command parameter*
        if message.startswith(':'):
            parts = protocol.ARGUMENT_SEPARATOR.split(message[1:], 2)
        else:
            parts = [ None ] + protocol.ARGUMENT_SEPARATOR.split(message, 1)

        if len(parts) == 3:
            source, command, raw_params = parts
        elif len(parts) == 2:
            source, command = parts
            raw_params = ''
        else:
            raise pydle.protocol.ProtocolViolation('Improper IRC message format: not enough elements.', message=message)

        # Sanity check for command.
        if not protocol.COMMAND_PATTERN.match(command):
            valid = False

        # Extract parameters properly.
        # Format: (word|:sentence)*

        # Only parameter is a 'trailing' sentence.
        if raw_params.startswith(protocol.TRAILING_PREFIX):
            params = [ raw_params[len(protocol.TRAILING_PREFIX):] ]
        # We have a sentence in our parameters.
        elif ' ' + protocol.TRAILING_PREFIX in raw_params:
            index = raw_params.find(' ' + protocol.TRAILING_PREFIX)

             # Get all single-word parameters.
            params = protocol.ARGUMENT_SEPARATOR.split(raw_params[:index].rstrip(' '))
            # Extract last parameter as sentence
            params.append(raw_params[index + len(protocol.TRAILING_PREFIX) + 1:])
        # We have some parameters, but no sentences.
        elif raw_params:
            params = protocol.ARGUMENT_SEPARATOR.split(raw_params)
        # No parameters.
        else:
            params = []

        # Commands can be either [a-zA-Z]+ or [0-9]+.
        # In the former case, force it to uppercase.
        # In the latter case (a numeric command), try to represent it as such.
        try:
            command = int(command)
        except ValueError:
            command = command.upper()

        # Return parsed message.
        return RFC1459Message(command, params, source=source, _valid=valid, _raw=message)

    def construct(self, force=False):
        """ Construct a raw IRC message. """
        # Sanity check for command.
        command = str(self.command)
        if not protocol.COMMAND_PATTERN.match(command) and not force:
            raise pydle.protocol.ProtocolViolation('The constructed command does not follow the command pattern ({pat})'.format(pat=protocol.COMMAND_PATTERN.pattern), message=command)
        message = command.upper()

        # Add parameters.
        if not self.params:
            message += ' '
        for idx, param in enumerate(self.params):
            # Trailing parameter?
            if not param or ' ' in param or param[0] == ':':
                if idx + 1 < len(self.params) and not force:
                    raise pydle.protocol.ProtocolViolation('Only the final parameter of an IRC message can be trailing and thus contain spaces, or start with a colon.', message=param)
                message += ' ' + protocol.TRAILING_PREFIX + param
            # Regular parameter.
            else:
                message += ' ' + param

        # Prepend source.
        if self.source:
            message = ':' + self.source + ' ' + message

        # Sanity check for characters.
        if any(ch in message for ch in protocol.FORBIDDEN_CHARACTERS) and not force:
            raise pydle.protocol.ProtocolViolation('The constructed message contains forbidden characters ({chs}).'.format(chs=', '.join(protocol.FORBIDDEN_CHARACTERS)), message=message)

        # Sanity check for length.
        message += protocol.LINE_SEPARATOR
        if len(message) > protocol.MESSAGE_LENGTH_LIMIT and not force:
            raise pydle.protocol.ProtocolViolation('The constructed message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=protocol.MESSAGE_LENGTH_LIMIT), message=message)

        return message


def normalize(input, case_mapping=protocol.DEFAULT_CASE_MAPPING):
    """ Normalize input according to case mapping. """
    if case_mapping not in protocol.CASE_MAPPINGS:
        raise pydle.protocol.ProtocolViolation('Unknown case mapping ({})'.format(case_mapping))

    input = input.lower()

    if case_mapping in ('rfc1459', 'rfc1459-strict'):
        input = input.replace('{', '[').replace('}', ']').replace('|', '\\')
    if case_mapping == 'rfc1459':
        input = input.replace('~', '^')

    return input

class NormalizingDict(collections.abc.MutableMapping):
    """ A dict that normalizes entries according to the given case mapping. """
    def __init__(self, *args, case_mapping):
        self.storage = {}
        self.case_mapping = case_mapping
        self.update(dict(*args))

    def __getitem__(self, key):
        if not isinstance(key, str):
            raise KeyError(key)
        return self.storage[normalize(key, case_mapping=self.case_mapping)]

    def __setitem__(self, key, value):
        if not isinstance(key, str):
            raise KeyError(key)
        self.storage[normalize(key, case_mapping=self.case_mapping)] = value

    def __delitem__(self, key):
        if not isinstance(key, str):
            raise KeyError(key)
        del self.storage[normalize(key, case_mapping=self.case_mapping)]

    def __iter__(self):
        return iter(self.storage)

    def __len__(self):
        return len(self.storage)

    def __repr__(self):
        return '{mod}.{cls}({dict}, case_mapping={cm})'.format(
            mod=__name__, cls=self.__class__.__name__,
            dict=self.storage, cm=self.case_mapping)


# Parsing.

def parse_user(raw):
    """ Parse nick(!user(@host)?)? structure. """
    nick = raw
    user = None
    host = None

    # Attempt to extract host.
    if protocol.HOST_SEPARATOR in raw:
        raw, host = raw.split(protocol.HOST_SEPARATOR)
    # Attempt to extract user.
    if protocol.USER_SEPARATOR in raw:
        nick, user = raw.split(protocol.USER_SEPARATOR)

    return nick, user, host

def parse_modes(modes, current, behaviour):
    """ Parse mode change string(s) and return updated dictionary. """
    current = current.copy()
    modes = modes[:]

    # Iterate in a somewhat odd way over the list because we want to modify it during iteration.
    i = 0
    while i < len(modes):
        piece = modes[i]
        add = True
        sigiled = False

        for mode in piece:
            # Set mode to addition or deletion of modes.
            if mode == '+':
                add = True
                sigiled = True
                continue
            if mode == '-':
                add = False
                sigiled = True
                continue

            # Find mode behaviour.
            for type, affected in behaviour.items():
                if mode in affected:
                    break
            else:
                # If we don't have a behaviour for this mode, assume it has no parameters...
                type = protocol.BEHAVIOUR_NO_PARAMETER

            # Don't parse modes that are meant for list retrieval.
            if type == protocol.BEHAVIOUR_LIST and not sigiled:
                continue

            # Do we require a parameter?
            if type in (protocol.BEHAVIOUR_PARAMETER, protocol.BEHAVIOUR_LIST) or (type == protocol.BEHAVIOUR_PARAMETER_ON_SET and add):
                # Do we _have_ a parameter?
                if i + 1 == len(modes):
                    raise pydle.protocol.ProtocolViolation('Attempted to parse mode with parameter ({s}{mode}) but no parameters left in mode list.'.format(
                        mode=mode, s='+' if add else '-'), ' '.join(modes))
                param = modes.pop(i + 1)

            # Now update the actual mode dict with our new values.
            if type in (protocol.BEHAVIOUR_PARAMETER, protocol.BEHAVIOUR_LIST):
                # Add/remove parameter from list.
                if add:
                    if mode not in current:
                        current[mode] = []
                    current[mode].append(param)
                else:
                    if mode in current and param in current[mode]:
                        current[mode].remove(param)
            elif type == protocol.BEHAVIOUR_PARAMETER_ON_SET and add:
                # Simply set parameter.
                current[mode] = param
            else:
                # Simply add/remove option.
                if add:
                    current[mode] = True
                else:
                    if mode in current:
                        del current[mode]
        i += 1

    return current
