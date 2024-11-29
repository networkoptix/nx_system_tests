# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from configparser import ConfigParser
from io import StringIO

_logger = logging.getLogger(__name__)


def update_conf_file(path, new_configuration):
    old_config = path.read_text(encoding='ascii')
    config = ConfigParser()
    config.optionxform = lambda a: a  # Configuration is case-sensitive.
    config.read_file(StringIO(old_config))
    for name, value in new_configuration.items():
        if value is None:
            config.remove_option('General', name)
        else:
            config.set('General', name, str(value))
    f = StringIO()  # TODO: Should be text.
    config.write(f)
    _logger.debug('Write config to %s:\n%s', path, f.getvalue())
    path.write_text(f.getvalue())
