import colorlog
import logging
from logging import DEBUG, INFO, WARNING, CRITICAL, ERROR

from lexios.settings.main import LOG_FOLDER, LOGS_VERBOSITY_LEVEL, CONSOLE_VERBOSITY_LEVEL

class CustomLogger:
    log_path = LOG_FOLDER

    def __init__(self, log_type):
        self.logger = logging.getLogger(log_type)
        self.logger.setLevel(logging.getLevelName(LOGS_VERBOSITY_LEVEL))

        # Check if handlers already exist
        if not self.logger.handlers:

            file_formatter = logging.Formatter('%(levelname)s - %(asctime)s - %(message)s')

            console_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(levelname)s - %(asctime)s - %(message)s',
                datefmt=None,
                reset=True,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                },
                secondary_log_colors={},
                style='%'
            )

            # File handler
            file_handler = logging.FileHandler(f'{self.log_path}/log_{log_type}.log')
            file_handler.setFormatter(file_formatter)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

            # Set the log level for the console handler once during initialization
            console_handler.setLevel(logging.getLevelName(CONSOLE_VERBOSITY_LEVEL))  # Set to ERROR by default

    def log_message(self, level, message, details=None):

        level = logging.getLevelName(level).lower()
        
        if details is not None:
            message = f"{message} - {str(details)}"

        getattr(self.logger, level)(message)

    def debug(self, message, details=None):
        self.log_message(DEBUG, message, details)

    def info(self, message, details=None):
        self.log_message(INFO, message, details)

    def warning(self, message, details=None):
        self.log_message(WARNING, message, details)

    def error(self, message, details=None):
        self.log_message(ERROR, message, details)

    def critical(self, message, details=None):
        self.log_message(CRITICAL, message, details)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Code to clean up resources, if needed
        pass

# Usage
if __name__ == "__main__":
# Example usage with context manager
    with CustomLogger('example') as logger:
        logger.debug('This is a debug message')
        logger.info('This is an info message')
        logger.warning('This is a warning message')
        logger.error('This is an error message')
        logger.critical('This is a critical message')