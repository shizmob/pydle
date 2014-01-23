## protocol.py
# IRC low-level protocol constants and helpers.
import re
import collections

## Own definitions.

# While this *technically* is supposed to be 143/994, I've yet to see a server that actually uses those.
DEFAULT_PORT = 6667
DEFAULT_TLS_PORT = 6697

FALLBACK_ENCODING = 'iso-8859-1'

## Limits.
CHANNEL_LIMITS_GROUPS = { '#': frozenset('#&'), '&': frozenset('#&') }
CHANNEL_LIMITS = { frozenset('#&'): 10 }
LIST_LIMIT_GROUPS = { 'b': frozenset('b') }
LIST_LIMITS = { frozenset('b'): None }
PARAMETER_LIMIT = 15
MESSAGE_LENGTH_LIMIT = 512
CHANNEL_LENGTH_LIMIT = 200
NICKNAME_LENGTH_LIMIT = 8
TOPIC_LENGTH_LIMIT = 450

## Defaults.

BEHAVIOUR_NO_PARAMETER = 'noparam'
BEHAVIOUR_PARAMETER = 'param'
BEHAVIOUR_PARAMETER_ON_SET = 'param_set'
BEHAVIOUR_LIST = 'list'

CHANNEL_MODES = { 'o', 'p', 's', 'i', 't', 'n', 'b', 'v', 'm', 'r', 'k', 'l' }
CHANNEL_MODES_BEHAVIOUR = { BEHAVIOUR_LIST: { 'b' }, BEHAVIOUR_PARAMETER: { 'o', 'v' }, BEHAVIOUR_PARAMETER_ON_SET: { 'k', 'l' }, BEHAVIOUR_NO_PARAMETER: { 'p', 's', 'i', 't', 'n', 'm', 'r' } }
CHANNEL_PREFIXES = { '#', '&' }
CASE_MAPPINGS = { 'ascii', 'rfc1459', 'strict-rfc1459' }
CASE_MAPPING = 'rfc1459'
NICKNAME_PREFIXES = collections.OrderedDict([('@', 'o'), ('+', 'v')])
USER_MODES = { 'i', 'w', 's', 'o' }
# Maybe one day, user modes will have parameters...
USER_MODES_BEHAVIOUR = { BEHAVIOUR_NO_PARAMETER: { 'i', 'w', 's', 'o' } }

## Message parsing.

FORBIDDEN_CHARACTERS = { '\r', '\n', '\0' }

LINE_SEPARATOR = '\r\n'
MINIMAL_LINE_SEPARATOR = '\n'
USER_SEPARATOR = '!'
HOST_SEPARATOR = '@'

PRIVATE_CHANNEL_SIGIL = '@'
SECRET_CHANNEL_SIGIL = '*'
PUBLIC_CHANNEL_SIGIL = '='

ARGUMENT_SEPARATOR = re.compile(' +', re.UNICODE)
COMMAND_PATTERN = re.compile('^([a-zA-Z]+|[0-9]+)$', re.UNICODE)
TRAILING_PREFIX = ':'


## Errors.

class ProtocolViolation(Exception):
    """ An error that occurred while parsing or constructing an IRC message that violates the IRC protocol. """
    def __init__(self, msg, message):
        super().__init__(msg)
        self.irc_message = message


## Message parsing and construction.

# Construction.

def construct(command, *params, source=None):
    """ Construct a raw IRC message. """
    # Sanity check for command.
    command = str(command)
    if not COMMAND_PATTERN.match(command):
        raise ProtocolViolation('The constructed command does not follow the command pattern ({pat})'.format(pat=COMMAND_PATTERN.pattern), message=command)
    message = command.upper()

    # Add parameters.
    if not params:
        message += ' '
    for idx, param in enumerate(params):
        # Trailing parameter?
        if ' ' in param:
            if idx + 1 < len(params):
                raise ProtocolViolation('Only the final parameter of an IRC message can be trailing and thus contain spaces.', message=param)
            message += ' ' + TRAILING_PREFIX + param
        # Regular paramter.
        else:
            message += ' ' + param

    # Prepend source.
    if source:
        message = ':' + source + ' ' + message

    # Sanity check for characters.
    if any(ch in message for ch in FORBIDDEN_CHARACTERS):
        raise ProtocolViolation('The constructed message contains forbidden characters ({chs}).'.format(chs=', '.join(FORBIDDEN_CHARACTERS)), message=message)

    # Sanity check for length.
    message += LINE_SEPARATOR
    if len(message) > MESSAGE_LENGTH_LIMIT:
        raise ProtocolViolation('The constructed message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=MESSAGE_LENGTH_LIMIT), message=message)

    return message


# Validation.

def normalize(input, case_mapping='rfc1459'):
    """ Normalize input according to case mapping. """
    if case_mapping not in CASE_MAPPINGS:
        raise ProtocolViolation('Unknown case mapping ({})'.format(case_mapping))

    input = input.lower()

    if case_mapping in ('rfc1459', 'rfc1459-strict'):
        input = input.replace('{', '[').replace('}', ']').replace('|', '\\')
    if case_mapping == 'rfc1459':
        input = input.replace('~', '^')

    return input

def equals(left, right, case_mapping='rfc1459'):
    """ Determine whether or not the given nicknames are equal in the given case mapping. """
    if case_mapping not in CASE_MAPPINGS:
        raise ProtocolViolation('Unknown case mapping ({})'.format(case_mapping))

    return normalize(left, case_mapping) == normalize(right, case_mapping)


# Parsing.

def parse(line, encoding='utf-8'):
    """
    Parse given line into IRC message structure.
    Returns a tuple of (source, command, parameters), where parameters is a list.
    """
    # Decode message.
    try:
        message = line.decode(encoding)
    except UnicodeDecodeError:
        # Try our fallback encoding.
        message = line.decode(FALLBACK_ENCODING)

    # Sanity check for message length.
    if len(message) > MESSAGE_LENGTH_LIMIT:
        raise ProtocolViolation('The received message is too long. ({len} > {maxlen})'.format(len=len(message), maxlen=MESSAGE_LENGTH_LIMIT), message=message)

    # Strip message separator.
    if message.endswith(LINE_SEPARATOR):
        message = message[:-len(LINE_SEPARATOR)]
    elif message.endswith(MINIMAL_LINE_SEPARATOR):
        message = message[:-len(MINIMAL_LINE_SEPARATOR)]

    # Sanity check for forbidden characters.
    if any(ch in message for ch in FORBIDDEN_CHARACTERS):
        raise ProtocolViolation('The received message contains forbidden characters ({chs}).'.format(chs=', '.join(repr(x) for x in FORBIDDEN_CHARACTERS)), message=message)

    # Extract message sections.
    # Format: (:source)? command parameter*
    try:
        if message.startswith(':'):
            source, command, raw_params = ARGUMENT_SEPARATOR.split(message, 2)
            source = source[1:]
        else:
            command, raw_params = ARGUMENT_SEPARATOR.split(message, 1)
            source = None
    except ValueError:
        raise ProtocolViolation('Improper IRC message format: not enough elements.')

    # Sanity check for command.
    if not COMMAND_PATTERN.match(command):
        raise ProtocolViolation('The received command ({message}) is not a valid IRC command.'.format(message=command))

    # Extract parameters properly.
    # Format: (word|:sentence)*

    # Only parameter is a 'trailing' sentence.
    if raw_params.startswith(TRAILING_PREFIX):
        params = [ raw_params[len(TRAILING_PREFIX):] ]
    # We have a sentence in our parameters.
    elif ' ' + TRAILING_PREFIX in raw_params:
        index = raw_params.find(' ' + TRAILING_PREFIX)

         # Get all single-word parameters.
        params = ARGUMENT_SEPARATOR.split(raw_params[:index].rstrip(' '))
        # Extract last parameter as sentence
        params.append(raw_params[index + len(TRAILING_PREFIX) + 1:])
    # We have some parameters, but no sentences.
    elif raw_params:
        params = ARGUMENT_SEPARATOR.split(raw_params)
    # No parameters.
    else:
        params = []

    # Commands can be either [a-zA-Z]+ or [0-9]+.
    # In the former case, force it to yppwecase.
    # In the latter case (a numeric command), try to represent it as such.
    try:
        command = int(command)
    except ValueError:
        command = command.upper()

    # Return parsed message.
    return (source, command, params)

def parse_user(raw):
    """ Parse nick(!user(@host)?)? structure. """
    nick = raw
    user = None
    host = None

    # Attempt to extract host.
    if HOST_SEPARATOR in raw:
        raw, host = raw.split(HOST_SEPARATOR)
    # Attempt to extract user.
    if USER_SEPARATOR in raw:
        nick, user = raw.split(USER_SEPARATOR)

    return nick, user, host

def parse_user_modes(modes, current):
    """ Parse user mode changes and return updated mode dictionary. """
    return parse_modes(modes, current, behaviour=USER_MODES_BEHAVIOUR)

def parse_channel_modes(modes, current, behaviour=CHANNEL_MODES_BEHAVIOUR):
    """ Parse channel mode changes and return updated mode dictionary. """
    return parse_modes(modes, current, behaviour=behaviour)

def parse_modes(modes, current, behaviour):
    """ Parse mode change string(s) and return updated dictionary. """
    current = current.copy()

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
                type = BEHAVIOUR_NO_PARAMETER

            # Don't parse modes that are meant for list retrieval.
            if type == BEHAVIOUR_LIST and not sigiled:
                continue

            # Do we require a parameter?
            if type in (BEHAVIOUR_PARAMETER, BEHAVIOUR_LIST) or (type == BEHAVIOUR_PARAMETER_ON_SET and add):
                # Do we _have_ a parameter?
                if i + 1 == len(modes):
                    raise ProtocolViolation(
                        'Attempted to parse mode with parameter ({s}{mode}) but no parameters left in mode list.'.format(
                        mode=mode, s='+' if add else '-'), ' '.join(modes))
                param = modes.pop(i + 1)

            # Now update the actual mode dict with our new values.
            if type in (BEHAVIOUR_PARAMETER, BEHAVIOUR_LIST):
                # Add/remove parameter from list.
                if add:
                    if mode not in current:
                        current[mode] = []
                    current[mode].append(param)
                else:
                    if mode in current and param in current[mode]:
                        current[mode].remove(param)
            elif type == BEHAVIOUR_PARAMETER_ON_SET and add:
                # Simply set parameter.
                current[mode] = param
            else:
                # Simply add/remove option.
                if add:
                    current[mode] = True
                else:
                    if mode in current:
                        del current[mode]

        # Onto the next mode.
        i += 1

    return current

