# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import logging.handlers
from pathlib import Path
from urllib.parse import urlparse


def init_logging(process_uri: str):
    logging.getLogger().setLevel(logging.DEBUG)
    log_file_relative_path = urlparse(process_uri).path.strip('/') + '.log'
    _init_file_logging(log_file_relative_path)
    _init_stream_logging()


def _init_file_logging(log_file_relative_path: str):
    service_log_dir = Path('~/.cache/infrastructure_logs').expanduser()
    service_log_dir.mkdir(exist_ok=True)
    log_file = service_log_dir / log_file_relative_path
    log_file.parent.mkdir(exist_ok=True, parents=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=200 * 1024**2, backupCount=6)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)


def _init_stream_logging():
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(stream_handler)
