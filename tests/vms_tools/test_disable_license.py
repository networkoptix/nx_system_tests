# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles import licensing


def _test_disable_license(distrib_url):
    license_server = licensing.get_remote_licensing_server()
    license_key = license_server.generate({'BRAND2': 'hdwitness'})
    license_server.disable(license_key)
    response = license_server.info(license_key)
    assert not response['body']['is_enabled']
