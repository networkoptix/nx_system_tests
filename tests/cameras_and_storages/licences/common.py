# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from installation import Mediaserver


def key_is_absent(server: Mediaserver, key: str) -> bool:
    licenses = server.api.list_licenses()
    return key not in [license.key for license in licenses]
