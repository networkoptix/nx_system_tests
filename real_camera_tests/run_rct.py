# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
import re
import sys
from contextlib import ExitStack
from datetime import datetime
from ipaddress import IPv4Interface
from ipaddress import ip_interface
from typing import Collection
from typing import Sequence

from _internal.service_registry import elasticsearch
from _internal.service_registry import qa_video_store
from ca import default_ca
from config import global_config
from directories import clean_up_artifacts
from directories import get_run_dir
from directories import make_artifact_store
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import make_mediaserver_installation
from mediaserver_api import MediaserverApiV1
from mediaserver_api import MediaserverApiV2
from mediaserver_scenarios.distrib_argparse_action import DistribArgparseAction
from real_camera_tests._expected_cameras import ExpectedCameras
from real_camera_tests._expected_cameras import expected_cameras_parent
from real_camera_tests._stand import Stand
from real_camera_tests.ifaddr import get_local_ipv4_interfaces
from real_camera_tests.reporter import CheckResults
from real_camera_tests.reporter import RctElasticReporter
from real_camera_tests.reporter import RctLocalReporter
from vm.default_vm_pool import public_default_vm_pool
from vm.virtual_box import VBoxAccessSettings
from vm.virtual_box import VBoxLinux

_logger = logging.getLogger(__name__)


def main(args: Sequence[str]):
    parsed_args = _parse_args(args)
    installers_url = parsed_args.distrib_url
    clean_up_artifacts()
    run_dir = get_run_dir()
    check_results = CheckResults()
    check_results.store_run_info(
        run_vms_url=installers_url,
        artifacts_url=make_artifact_store().store_one(run_dir),
        started_at_iso=datetime.utcnow().isoformat(' ', 'microseconds'),
        )
    file_handler = logging.FileHandler(run_dir / 'rct_debug.log', encoding='utf-8')
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s '
            '%(threadName)10s '
            '%(name)s '
            '%(levelname)s '
            '%(message)s'))
    logging.root.addHandler(file_handler)
    _logger.info("Artifacts dir: %s", run_dir.absolute())
    installer_supplier = ClassicInstallerSupplier(installers_url)
    interface = global_config['interface']
    interfaces = set(get_local_ipv4_interfaces())
    if interface not in interfaces:
        raise ValueError(f"RCT interface choices: {interfaces}")
    vm_ip_settings_as_str = global_config.get(
        'vm_ip_settings',
        '10.1.1.1/24;192.168.10.1/24;10.0.252.10/29',
        )
    vm_ip_settings = [ip_interface(part) for part in vm_ip_settings_as_str.split(';')]
    expected_cameras = expected_cameras_parent / global_config['expected_cameras']
    vlc_serving_ip = _find_local_address_for_serving(vm_ip_settings)
    gpio_server_addr = global_config.get('gpio_server_addr', '10.0.0.36:8080')
    vm_pool = public_default_vm_pool(run_dir)
    with ExitStack() as stack:
        vm = stack.enter_context(
            vm_pool.clean_vm(
                VBoxLinux(
                    name='ubuntu22',
                    ram_mb=14366,
                    cpu_count=4,
                    access_settings=VBoxAccessSettings({
                        'tcp': {1: 7001, 2: 22},
                        'udp': {5: 5353},
                        }))))
        vm.ensure_started(run_dir)
        os_access = vm.os_access
        stack.enter_context(vm.os_access.prepared_one_shot_vm(run_dir))
        stack.callback(vm.vm_control.copy_logs, run_dir)
        nic_id = vm.vm_control.plug_bridged(interface)
        os_access.networking.enable_interface(nic_id)
        os_access.networking.wait_for_link(nic_id)
        os_access.networking.setup_static_ip(nic_id, *vm_ip_settings)
        for ip in vm_ip_settings:
            os_access.networking.allow_subnet_unicast(str(ip.network))
            os_access.networking.allow_subnet_broadcast(str(ip.network))
        os_access.networking.allow_multicast()  # Multicast for discovery.
        mediaserver = make_mediaserver_installation(os_access, installer_supplier.distrib().customization())
        stack.callback(mediaserver.collect_artifacts, run_dir)
        installer = installer_supplier.upload_server_installer(os_access)
        license_server = LocalLicenseServer()
        license_server = stack.enter_context(license_server.serving())
        mediaserver.allow_license_server_access(license_server.url())
        default_ca().add_to_env_vars()
        mediaserver.install(installer)
        # Trying to update *.ini before installing Mediaserver to avoid doing stop/start operations
        # fails due to attempt to open .../mediaserver/build_info.txt in Installation.get_version()
        mediaserver.stop()
        mediaserver.update_conf({
            'checkForUpdateUrl': 'http://127.0.0.1:8080',  # TODO: Use fake server responding with small updates.
            # This setting is required to fast camera disconnect, for more details, please see
            # https://networkoptix.atlassian.net/browse/VMS-14345
            'retryCountToMakeCameraOffline': 1,
            'mediaStatisticsMaxDurationInFrames': 125,
            'mediaStatisticsWindowSize': 12,
            'resourceInitThreadsCount': 200,
            'onlineResourceDataEnabled': 0,
            })
        mediaserver.set_max_log_file_size(limit_bytes=2 ** 30)  # 1 GB
        mediaserver.update_ini('resource_management', {'cameraDiscoveryIntervalMs': 500})
        mediaserver.init_key_pair(default_ca().generate_key_and_cert(os_access.address))
        mediaserver.update_ini('nx_utils', {'assertCrash': 0, 'assertHeavyCondition': 0})
        mediaserver.set_main_log_level('verbose')
        mediaserver.update_conf({'retryCountToMakeCameraOffline': None})
        api_cls = (
            MediaserverApiV1 if installer_supplier.distrib().older_than('vms_5.1')
            else MediaserverApiV2)
        mediaserver.init_api(api_cls(mediaserver.base_url()))
        mediaserver.start()
        mediaserver.api.setup_local_system(
            system_settings={
                'insecureDeprecatedApiEnabled': 'true',
                'licenseServer': license_server.url(),
                },
            basic_and_digest_auth_required=True,
            )
        brand = mediaserver.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
        mediaserver.api.activate_license(key)
        stand = Stand(
            server=mediaserver,
            expected_cameras=ExpectedCameras(expected_cameras, camera_filter_re=re.compile('.*')),
            interface=interface,
            vlc_serving_ip=vlc_serving_ip,
            os_access=os_access,
            stage_hard_timeout=3600,
            check_results=check_results,
            gpio_server_address=gpio_server_addr,
            )
        stand.check_connection_by_ip_address(os_access)
        stand.set_vlc_hosts()
        stand.check_connection_by_host_alias(os_access)
        for config in stand.expected_cameras.generic_link_configs:
            stack.enter_context(config.serving(qa_video_store, vlc_serving_ip))
        stand.check_ports_opened_by_libvlc(os_access)
        local_reporter = RctLocalReporter(run_dir / f'{mediaserver.get_version()}_test_results.json')
        elastic_reporter = RctElasticReporter(elasticsearch, mediaserver.get_version())
        stack.callback(check_results.save_result, local_reporter)
        stack.callback(check_results.save_result, elastic_reporter)
        stand.run_all_stages()
        # Examine before mediaserver is stopped: examination requires mediaserver be running.
        mediaserver.examine()
        mediaserver.output_metrics()
        # Try stopping mediaserver afterwards to check whether it won't hang. This can be
        # disabled to allow playing with working mediaserver after the tests end.
        mediaserver.stop()
        mediaserver.check_for_error_logs()


def _find_local_address_for_serving(ip_settings: Collection[IPv4Interface]):
    for adapter_addresses in get_local_ipv4_interfaces().values():
        for address in adapter_addresses:
            _logger.debug("Consider address for VLC: %s", address)
            for vm_ip_address in ip_settings:
                if address.network == vm_ip_address.network:
                    return address.ip
    raise RuntimeError("None of host's IP addresses is from RCT network. Can't test RTSP.")


def _parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--installers-url', action=DistribArgparseAction)
    return parser.parse_args(args)


if __name__ == '__main__':
    logging.root.setLevel(logging.NOTSET)
    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s ' + logging.BASIC_FORMAT))
    logging.root.addHandler(stream_handler)
    main(sys.argv[1:])
