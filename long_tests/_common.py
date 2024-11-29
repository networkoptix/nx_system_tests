# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from argparse import ArgumentParser
from contextlib import AbstractContextManager
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from typing import Mapping

from doubles.licensing.local_license_server import LocalLicenseServer
from installation import Mediaserver


@lru_cache
def get_installers_url():
    parser = ArgumentParser()
    parser.add_argument(
        '--installers-url',
        required=True,
        help="VMS installers URL that will be tested.")
    args, _ = parser.parse_known_args()
    return args.installers_url


@contextmanager
def license_server_running(mediaserver: Mediaserver) -> AbstractContextManager[str]:
    license_server = LocalLicenseServer()
    with license_server.serving():
        mediaserver.allow_license_server_access(license_server.url())
        mediaserver.api.set_license_server(license_server.url())
        license_key = license_server.generate({'QUANTITY2': 999})
        mediaserver.api.activate_license(license_key)
        yield license_key


@lru_cache
def get_build_info(mediaserver: Mediaserver) -> Mapping[str, Any]:
    build_info = mediaserver._build_info().as_dict()
    return {
        'installer_type': build_info['publicationType'],
        'version': build_info['version'],
        'change_set': build_info['changeSet'],
        'branch': build_info['branch'],
        'customization': build_info['customization'],
        }


_logger = logging.getLogger(__name__)
