# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import fnmatch
import logging
import socket
from configparser import ConfigParser
from pathlib import Path
from typing import Mapping

_logger = logging.getLogger(__name__)


def _read_config(*paths: Path) -> Mapping[str, str]:
    """Read and resolve overrides according to versions.

    Optionally add ";v123" to sections like "[sc-ft???;v45]".
    If not specified, "v0" is assumed.
    Higher versions override lower versions.

    New commit can override local per-host configs.
    New per-host configs can override config values on old commits.
    """
    config_parts = []
    for path_i, path in enumerate(paths):
        config_parser = ConfigParser()
        config_parser.read(path)
        host = socket.gethostname()
        sections = config_parser.sections()
        for section_i, section in enumerate(sections):
            mask, version = _parse_section_header(section)
            if fnmatch.fnmatch(host, mask):
                _logger.info("Config %s: section %s: read", path, section)
                items = config_parser.items(section)
                config_parts.append((version, path_i, section_i, items))
            else:
                _logger.debug("Config %s: section %s: skip", path, section)
    config_parts.sort()
    config = {}
    for _version, _path_i, _section_i, items in config_parts:
        config.update(items)
    return config


def _parse_section_header(section):
    if section == 'defaults':
        return '*', 0
    else:
        mask, semicolon, extra = section.partition(';')
        if not extra:
            return mask, 0
        elif extra.startswith('v'):
            try:
                return mask, int(extra[1:])
            except ValueError:
                raise ValueError(f"Cannot parse {extra} in {section}")
        else:
            raise ValueError(f"Unknown {extra} in {section}")


global_config = _read_config(
    Path(__file__).with_name('config.ini'),
    Path('~/.config/nx_func_tests.ini').expanduser(),
    )

if __name__ == '__main__':
    for k, v in global_config.items():
        print(k + '=' + v)
