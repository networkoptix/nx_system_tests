# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles import licensing
from tests.infra import assert_raises


def _test_cannot_deactivate_not_active_license(distrib_url):
    license_server = licensing.get_remote_licensing_server()
    license_key = license_server.generate({'BRAND2': 'hdwitness'})
    with assert_raises(licensing.ValidationError):
        license_server.deactivate(license_key)
