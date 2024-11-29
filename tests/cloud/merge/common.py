# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.waiting import wait_for_truthy

TEST_SYSTEM_SETTINGS = {
    'cameraSettingsOptimization': 'false',
    'autoDiscoveryEnabled': 'false',
    'statisticsAllowed': 'false',
    }


def wait_for_settings_merge(one, two):
    wait_for_truthy(
        lambda: one.api.get_system_settings() == two.api.get_system_settings(),
        description='{} and {} response identically to /api/systemSettings'.format(one, two))
