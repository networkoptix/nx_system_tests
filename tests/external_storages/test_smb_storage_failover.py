# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from ipaddress import ip_network

from directories import get_run_dir
from doubles.dnssd import DNSSDWebService
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import MediaserversDNSSDScope
from mediaserver_scenarios.storage_preparation import add_smb_storage
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.waiting import wait_for_truthy


class test_v1(VMSTest):
    """Test get streams.

    TODO: Add the 'gitlab' tag after VMS-54711 fix
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57232
    """

    def _run(self, args, exit_stack):
        _test_storage_failover(args.distrib_url, 'v1', exit_stack)


def _test_storage_failover(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    smb_network = ip_network('10.254.1.0/24')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'smb', 'type': 'ubuntu22'},
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            ],
        'networks': {
            str(smb_network): {
                'smb': None,
                'first': None,
                },
            '10.254.2.0/24': {
                'first': None,
                'second': None,
                },
            },
        'mergers': [{
            'local': 'first',
            'remote': 'second',
            'take_remote_settings': True,
            'network': '10.254.2.0/24',
            }],
        }))
    camera_server = MultiPartJpegCameraServer()
    [system, _, interfaces] = network_and_system
    one = system['first']
    two = system['second']
    smb_server = system['smb']

    one.api.enable_failover()
    two.api.enable_failover()

    [default_storage] = one.api.list_storages()
    one.api.disable_storage(default_storage.id)

    camera_server_ip = one.os_access.source_address()
    records = [DNSSDWebService('camera', camera_server_ip, camera_server.port, '/ft_cam.mjpeg')]

    wait_for_camera_to_appear(one.api, one, records)

    [smb_server_address, smb_server_nic_id] = interfaces['smb'][smb_network]
    add_smb_storage(one.api, smb_server.os_access, str(smb_server_address))

    smb_server.os_access.networking.disable_interface(smb_server_nic_id)
    # Failover takes a lot of time.
    # See: https://networkoptix.atlassian.net/browse/VMS-54711
    wait_for_camera_to_appear(two.api, two, records)


def wait_for_camera_to_appear(server_api, mediaserver: Mediaserver, records):
    server_id = server_api.get_server_id()
    scope = MediaserversDNSSDScope([mediaserver])
    started_at = time.monotonic()
    for _ in range(30):
        scope.advertise_once(records)
        [camera] = wait_for_truthy(server_api.list_cameras, description="Camera is discovered")
        if camera.parent_id == server_id:
            _logger.info("Camera appeared on server after %d seconds", time.monotonic() - started_at)
            break
        time.sleep(10)
    else:
        raise RuntimeError(
            f"Camera didn't appear on server after {(time.monotonic() - started_at):.0f} seconds")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v1()]))
