# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import sys
from typing import Sequence

from vm.virtual_box.configuration.build_base_snapshot import get_snapshot


def main(args: Sequence[str]):
    """Collect APT packages or any other prerequisites that requires Internet access.

    If you need to include or exclude some Ubuntu packages,
    you should run this script LOCALLY with Internet access
    and then upload the finalized `.tar.gz` file to the `/software` folder of prerequisites store.
    """
    logging.basicConfig(level=logging.INFO)
    if os.getenv('DRY_RUN'):
        _logger.info("Dry Run: Would collect base image prerequisites, args %s", args)
        return 0
    [build_os] = args
    snapshot = get_snapshot(build_os)
    snapshot.collect_prerequisites()


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
