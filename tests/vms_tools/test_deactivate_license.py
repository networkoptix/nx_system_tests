# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles import licensing


def _test_deactivate_license(distrib_url):
    license_server = licensing.get_remote_licensing_server()
    # ATTENTION! Hardware id isn't a random hash.
    # You can use any existing mediaserver to get a hardware id
    # At the moment, it's from one of QA mediaservers
    # http://10.0.3.14:7001/ec2/getHardwareIdsOfServers
    hardware_id = "05a2621ed9869128238186395a7078f45c"
    test_license_key = license_server.generate({'BRAND2': 'hdwitness', 'ORDERTYPE': 'test'})
    license_server.activate(test_license_key, hardware_id)
    response = license_server.info(test_license_key)
    assert response['body']['activations']
    license_server.deactivate(test_license_key)
    response = license_server.info(test_license_key)
    assert not response['body']['activations']
