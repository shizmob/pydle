# logging.py
# Thin wrapper around Python's (atrocious) logging module.
import logging

__all__ = [ 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL', 'Logger' ]


# Log levels.
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG


class Logger:
    """
    Thin wrapper around Python's rather atrocious logging module in order to make it more bearable.
    Formats messages automatically according to advanced string formatting, handles logger name and logfile changes painlessly.
    """
    FORMAT = '{asctime} [{name}] {levelname}: {message}'
    DATE_FORMAT = None
    FILE = None
    LEVEL = logging.WARNING

    def __init__(self, name=None, file=None, formatter=None):
        self._file = file or self.FILE
        self._formatter = formatter or logging.Formatter(self.FORMAT, datefmt=self.DATE_FORMAT, style='{')
        if name:
            self._name = name
            self.refresh_logger()

    def refresh_logger(self):
        """ Recreate logger instance. """
        self.logger = logging.Logger(self.name)
        self.setup_logger()

    def setup_logger(self):
        """ Set logger settings. """
        self.logger.setLevel(self.LEVEL)

        handler = logging.StreamHandler()
        handler.setFormatter(self.formatter)
        self.logger.addHandler(handler)

        if self.file:
            handler = logging.FileHandler(self.file)
            handler.setFormatter(self.formatter)
            self.logger.addHandler(handler)


    @property
    def name(self):
        """ This logger's identifier. """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.refresh_logger()

    @property
    def file(self):
        """ The file we are logging to, if any. """
        return self._file

    @file.setter
    def file(self, value):
        self._file = value
        self.refresh_logger()

    @property
    def formatter(self):
        """ The formatter we are using. """
        return self._formatter

    @formatter.setter
    def formatter(self, value):
        self._formatter = value
        self.refresh_logger()


    def debug(self, message, *args, **kwargs):
        """ Log DEBUG message. """
        self.logger.debug(message.format(*args, **kwargs))

    def inform(self, message, *args, **kwargs):
        """ Log INFO message. """
        self.logger.info(message.format(*args, **kwargs))

    def warn(self, message, *args, **kwargs):
        """ Log WARNING message. """
        self.logger.warning(message.format(*args, **kwargs))

    def err(self, message, *args, **kwargs):
        """ Log ERROR message. """
        self.logger.error(message.format(*args, **kwargs))

    def exception(self, exception):
        """ Log exception. """
        self.logger.exception(exception)

    def fatal(self, message, *args, **kwargs):
        """ Log FATAL message. """
        self.logger.fatal(message.format(*args, **kwargs))

