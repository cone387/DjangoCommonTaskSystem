import os
import logging
from logging.handlers import RotatingFileHandler


def add_file_handler(logger: logging.Logger, log_file=None, formatter=None, max_bytes=1024 * 1024 * 10,
                     encoding='utf-8', backup_count=5, clear_others=True, level=logging.INFO):
    if clear_others:
        logger.handlers.clear()
    if formatter is None:
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    if log_file is None:
        log_file = os.path.join(os.getcwd(), 'logs', logger.name + '.log')
    # if os.path.isfile(log_file):
    #     os.remove(log_file)
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, encoding=encoding, backupCount=backup_count)
    handler.setFormatter(formatter)
    if level is not None:
        logger.setLevel(level)
    logger.addHandler(handler)
    return log_file
