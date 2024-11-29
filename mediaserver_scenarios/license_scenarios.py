# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
def grant_license(mediaserver, license_server):
    mediaserver.allow_license_server_access(license_server.url())
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    mediaserver.api.activate_license(key)
