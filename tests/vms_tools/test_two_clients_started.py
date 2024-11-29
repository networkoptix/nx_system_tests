# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import DpkgClientInstallation
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_ubuntu22_linux_client_v0(VMSTest, CloudTest):
    """Test two clients started.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_two_clients_started(args.cloud_host, args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


def _test_two_clients_started(cloud_host, distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    [mediaserver_os_type, client_os_type] = two_vm_types
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [[_, _, client_vm], mediaserver_unit] = exit_stack.enter_context(
        pool.vm_and_mediaserver_vm_network((client_os_type, mediaserver_os_type)))
    client_installation = DpkgClientInstallation(
        client_vm.os_access,
        installer_supplier.distrib().customization(),
        installer_supplier.distrib().version(),
        cloud_host,
        )
    installer = installer_supplier.upload_client_installer(client_vm.os_access)
    client_installation.clean_certificates()
    client_installation.install(installer)
    client_installation.install_ca(default_ca().cert_path)
    server = mediaserver_unit.installation()
    server_ip = mediaserver_unit.subnet_ip()
    server.start()
    server.api.setup_local_system()
    server_url = server.api.url_with_another_host_and_port(server_ip, server.port)
    with client_installation.many_clients_running(server_url, client_count=2) as clients:
        [first_client, second_client] = clients
        first_connected_in = first_client.measure_connection_time(connect_timeout_sec=60)
        second_connected_in = second_client.measure_connection_time(connect_timeout_sec=60)
        _logger.info(
            "Connection time: %s, %s",
            first_connected_in, second_connected_in)
        assert first_connected_in is not None
        assert second_connected_in is not None
        assert first_connected_in != second_connected_in


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_linux_client_v0()]))
