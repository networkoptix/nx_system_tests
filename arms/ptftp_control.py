# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from arms.tftp_server_interface import TFTPServerControl


class LocalTFTPControl(TFTPServerControl):

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        self._tmp_file = config_dir / '.tmp'

    def set_tftp_root_for(self, ip_address: str, tftp_root: Path):
        _logger.info("%s: Set tftp root to %r for %r", self, str(tftp_root), ip_address)
        destination = self._config_dir / ip_address
        self._tmp_file.write_text(str(tftp_root) + '\n')
        self._tmp_file.replace(destination)  # 'Open + write' is not atomic while 'replace' is

    def __repr__(self):
        return f'<TFTPControl: {self._config_dir}>'


_logger = logging.getLogger(__name__)
