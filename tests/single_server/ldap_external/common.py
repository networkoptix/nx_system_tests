# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping

from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV3


def set_ldap_settings(api: MediaserverApi, ldap_settings: Mapping[str, str], api_version: str):
    if not api.server_older_than('vms_6.0') and api_version in ('v0', 'v1', 'v2'):
        # Starting with 6.0, only APIv3 can be used to configure LDAP settings.
        api_v3 = api.with_version(version_cls=MediaserverApiV3)
        api_v3.set_ldap_settings(**ldap_settings)
    else:
        api.set_ldap_settings(**ldap_settings)
