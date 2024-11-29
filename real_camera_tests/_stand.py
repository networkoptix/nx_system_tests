# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
import subprocess
import time
from contextlib import closing
from contextlib import contextmanager
from datetime import datetime
from ipaddress import IPv4Address

from installation import Mediaserver
from mediaserver_api import MediaserverApiConnectionError
from real_camera_tests import camera_stages
from real_camera_tests._expected_cameras import ExpectedCameras
from real_camera_tests.camera_stage import BaseStage
from real_camera_tests.camera_stage import MultiStage
from real_camera_tests.camera_stage import RealDeviceConfig
from real_camera_tests.camera_stage import Stage
from real_camera_tests.camera_stage import make_camera_step_generator
from real_camera_tests.camera_stages import IoMultiStage
from real_camera_tests.camera_stages import VideoExportMultiStage
from real_camera_tests.camera_stages import WrongPortDiscoveryStage
from real_camera_tests.checks import Halt
from real_camera_tests.checks import Skipped
from real_camera_tests.gpio.io_rpi import RemoteIoManager
from real_camera_tests.gpio.io_rpi import RemoteRewiringManager
from real_camera_tests.reporter import CheckResults
from real_camera_tests.server_stage import Run
from real_camera_tests.server_stages import auto_discovery_in_audit_trail
from real_camera_tests.server_stages import camera_count_metrics
from real_camera_tests.server_stages import cancel_auto_discovery
from real_camera_tests.server_stages import change_nvr_names
from real_camera_tests.server_stages import metrics_after
from real_camera_tests.server_stages import metrics_before
from real_camera_tests.server_stages import unexpected_cameras_after_autodiscovery
from real_camera_tests.server_stages import unexpected_cameras_after_manual_discovery

_logger = logging.getLogger(__name__)


class Stand:
    def __init__(
            self,
            server: Mediaserver,
            expected_cameras: ExpectedCameras,
            interface: str,
            vlc_serving_ip: IPv4Address,
            os_access,
            check_results: CheckResults,
            gpio_server_address: str,
            stage_hard_timeout=3600,
            ):
        self._stage_hard_timeout = stage_hard_timeout
        self._check_results = check_results
        self.server = server
        self.server_information = server.api.http_get('api/moduleInformation')
        self.interface = interface
        self._vlc_serving_ip = vlc_serving_ip
        self.os_access = os_access
        self.expected_cameras = expected_cameras
        self.run = Run(server, expected_cameras)
        self._gpio_server_address = gpio_server_address
        for config in self.expected_cameras.skipped_camera_configs:
            self._check_results.update_result(
                device_name=config.name,
                stage_name='general',
                result=Skipped(f"Camera {config.name} was excluded out by filter"),
                )

    def _setup_gpio_device(self, rewiring_manager):
        for config in self.expected_cameras.filtered_camera_configs:
            if not isinstance(config, RealDeviceConfig):
                continue
            for input in config.new_ins:
                rewiring_manager.connect_device_input_pin(
                    config.name, input.pin_name, input.channel)
            for output in config.new_outs:
                rewiring_manager.connect_device_output_pin(
                    config.name, output.pin_name, output.channel)

    def _run_server_stage(self, func, name=None):
        if name is None:
            name = func.__name__
        self.server.take_backtrace(f'{name}_before')
        _logger.info(
            "%s: %s: stage started",
            name, self.expected_cameras.server_config.name)
        self._check_results.update_result(
            device_name=self.expected_cameras.server_config.name,
            stage_name=name,
            result=Halt('Just started'),
            started_at_iso=datetime.utcnow().isoformat(' ', 'microseconds'),
            )
        started_at = time.monotonic()
        result = func(self.run)
        duration_sec = time.monotonic() - started_at
        message = result.get_text_result()
        _logger.info(
            "%s: %s: stage finished: %r",
            self.expected_cameras.server_config.name, name, message)
        self._check_results.update_result(
            device_name=self.expected_cameras.server_config.name,
            stage_name=name,
            result=result,
            duration_sec=duration_sec,
            )
        self.server.take_backtrace(f'{name}_after')

    def run_all_stages(self):
        _logger.info(
            'Stand run with %s cameras', self.expected_cameras.filtered_camera_count)
        self._run_server_stage(metrics_before)
        self._run_camera_stages(
            Stage(camera_stages.auto_discovery, timeout=180),
            Stage(camera_stages.attributes_auto, timeout=60),
            MultiStage(camera_stages.stream_auto, timeout=180),
            )
        self._run_server_stage(change_nvr_names)
        self._run_server_stage(auto_discovery_in_audit_trail, 'auto_discovery_in_audit_trail')
        self._run_server_stage(unexpected_cameras_after_autodiscovery)
        self._run_server_stage(cancel_auto_discovery)
        self._run_camera_stages(WrongPortDiscoveryStage(timeout=120))
        self._run_camera_stages(
            Stage(camera_stages.manual_discovery, timeout=600),
            Stage(camera_stages.camera_manually_added_in_audit_trail, timeout=60),
            Stage(camera_stages.attributes_manual, timeout=60),
            Stage(camera_stages.camera_metrics),
            MultiStage(camera_stages.stream_manual, timeout=180),
            VideoExportMultiStage(timeout=600),
            Stage(camera_stages.fps_is_max_when_no_record, timeout=180),
            # Avoid running view_live_in_audit_trail right after camera discovery: Server might
            # apply default stream settings on the camera while client is watching the live stream
            # resulting in RTSP connection shutdown.
            Stage(camera_stages.view_live_in_audit_trail, timeout=90),
            Stage(camera_stages.stream_urls),
            MultiStage(camera_stages.audio_stream, timeout=90),
            Stage(camera_stages.io_events),
            )
        rewiring_manager = RemoteRewiringManager(self._gpio_server_address)
        if rewiring_manager.is_accessible():
            self._setup_gpio_device(rewiring_manager)
            self._run_camera_stages(IoMultiStage(RemoteIoManager(self._gpio_server_address)))
        else:
            _logger.warning(
                "GPIO device on %s inaccessible; IoMultiStage not run", self._gpio_server_address)
        self._run_camera_stages(
            Stage(camera_stages.ptz_positions, timeout=60),
            Stage(camera_stages.change_device_name, timeout=60),
            Stage(camera_stages.change_logical_id),
            )
        self._run_server_stage(camera_count_metrics)
        self._run_server_stage(unexpected_cameras_after_manual_discovery)
        self._run_server_stage(metrics_after)
        time.sleep(60)
        self._run_server_stage(metrics_after, 'metrics_delayed')

    def all_cameras(self):
        return {
            cam.identity: cam.raw_data
            for cam in self.server.api.list_cameras()
            }

    def _run_camera_stages(self, discovery_stage: BaseStage, *stages: BaseStage):
        _logger.info('Run camera stages: %r', stages)
        step_generators = {
            camera_config.name: make_camera_step_generator(
                server=self.server,
                discovery_stage=discovery_stage,
                stages=stages,
                camera_config=camera_config,
                check_results=self._check_results,
                stage_hard_timeout=self._stage_hard_timeout,
                )
            for camera_config
            in self.expected_cameras.filtered_camera_configs
            }
        exhausted_generators = {}
        while True:
            self._log_statistics()
            active_generators = {}
            for name, step_generator in step_generators.items():
                try:
                    next(step_generator)
                except StopIteration:
                    exhausted_generators[name] = step_generator
                else:
                    active_generators[name] = step_generator
            _logger.debug(
                "Camera round complete: active=%r, finished=%r",
                [*active_generators.values()],
                [*exhausted_generators.values()],
                )
            if not active_generators:
                break
            step_generators = active_generators
            _logger.debug("Sleep for a while before the next round")
            time.sleep(1)

    def _log_statistics(self):
        message = 'Server performance statistics'
        try:
            stats = self.server.api.get_server_statistics()['statistics'][:3]
        except MediaserverApiConnectionError as error:
            _logger.debug(message + ': {!s}'.format(error))
        else:
            out = {s['description']: s['value'] for s in stats}
            out['HDD'] = out.get('sda')
            _logger.debug(message + ': CPU {CPU}, RAM {RAM}, HDD {HDD}'.format(**out))

    def set_vlc_hosts(self):
        """Add the bound address to /etc/hosts on the Mediaserver VM.

        Generic camera URLs look like: "proto://alias:port".

        Used for adding generic RTSP links, whose hostnames are aliases
        intended to point to the address which VLC is bound to and listens on.
        """
        if not self.expected_cameras.generic_link_configs:
            _logger.info("No generic links configs in filtered configs; skip setting host aliases")
            return
        generic_link_hostnames = {
            config.hostname for config in self.expected_cameras.generic_link_configs}
        self.os_access.set_hosts(
            {str(self._vlc_serving_ip): generic_link_hostnames},
            append=True,
            )

    def ping_host_from_vm(self, os_access):
        os_access.networking.ping(str(self._vlc_serving_ip))

    @staticmethod
    @contextmanager
    def _listening_tcp_socket(ip, port):
        _logger.info("Listen for test connection: %s:%d", ip, port)
        with closing(socket.socket()) as s:
            s.bind((ip, port))
            s.listen()
            yield

    @staticmethod
    def _check_tcp_handshake(os_access, host, port):
        for attempt in range(10):  # Usually enough.
            _logger.info("Connect: addr=%s:%d attempt=%d", host, port, attempt)
            try:
                os_access.run(f'nc -zv -w1 {host} {port}')
            except subprocess.CalledProcessError:
                time.sleep(1)
                continue
            return True
        return False

    @staticmethod
    def _check_udp_packet(os_access, ip, port):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            s.setblocking(False)
            s.bind((ip, port))
            for attempt in range(10):  # Usually enough.
                _logger.info("Send: addr=%s:%d attempt=%d", ip, port, attempt)
                os_access.run(f'nc -uv -w1 {ip} {port}', input=b'test')
                try:
                    s.recvfrom(100)
                except BlockingIOError:
                    continue
                return True
            return False

    def check_connection_by_ip_address(self, os_access):
        ip_address = str(self._vlc_serving_ip)
        for config in self.expected_cameras.generic_link_configs:
            with self._listening_tcp_socket(ip_address, config.port):
                if not self._check_udp_packet(os_access, ip_address, config.port):
                    raise Exception(
                        f"Cannot receive UDP packet at {ip_address}:{config.port}; "
                        f"check the firewalls on the host and the VM")
                if not self._check_tcp_handshake(os_access, ip_address, config.port):
                    raise Exception(
                        f"Cannot connect via TCP to {ip_address}:{config.port}; "
                        f"check the firewalls on the host and the VM")

    def check_connection_by_host_alias(self, os_access):
        ip_address = str(self._vlc_serving_ip)
        for config in self.expected_cameras.generic_link_configs:
            with self._listening_tcp_socket(ip_address, config.port):
                if not self._check_tcp_handshake(os_access, config.hostname, config.port):
                    raise Exception(
                        f"Cannot connect to {config.hostname}:{config.port}; "
                        f"check the hosts file on the VM")

    def check_ports_opened_by_libvlc(self, os_access):
        for config in self.expected_cameras.generic_link_configs:
            if not self._check_tcp_handshake(os_access, config.hostname, config.port):
                raise Exception(
                    f"Cannot connect to {config.hostname}:{config.port}; "
                    f"check that libvlc have opened ports")
