# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from distrib import Customization
from installation._base_installation import OsNotSupported
from installation._dpkg_server_installation import DpkgServerInstallation
from installation._mediaserver import Mediaserver
from installation._windows_server_installation import WindowsServerInstallation
from os_access import OsAccess


def make_mediaserver_installation(os_access: OsAccess, customization: Customization) -> Mediaserver:
    factories = [
        lambda: DpkgServerInstallation(os_access, customization),
        lambda: WindowsServerInstallation(os_access, customization),
        ]
    for factory in factories:
        try:
            return factory()
        except OsNotSupported:
            continue
    raise ValueError("No installation types exist for {!r}".format(os_access))


def find_mediaserver_installation(os_access: OsAccess) -> Mediaserver:
    for installation_class in [DpkgServerInstallation, WindowsServerInstallation]:
        try:
            return installation_class.find(os_access)
        except OsNotSupported:
            continue
    raise ValueError(f"No installation types exist for {os_access}")
