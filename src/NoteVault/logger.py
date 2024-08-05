import logging

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGING_FORMAT = '%(asctime)s | %(levelname)-8s | %(message)s'
VERBOSE = 15

def configure_logger(logger: logging.Logger, verbose: int = 0) -> None:
    level: int = logging.INFO if not verbose else VERBOSE if verbose == 1 else logging.DEBUG
    logging.addLevelName(VERBOSE, "VERBOSE")
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt=LOGGING_FORMAT,
                                           datefmt=DATE_FORMAT))
    logger.setLevel(level)
    logger.addHandler(handler)
