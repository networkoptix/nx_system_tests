# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import suppress
from pathlib import Path
from typing import List
from typing import Tuple
from typing import cast

from gui.mobile_ui.main_window import MainWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID
from installation._base_installation import BaseInstallation
from installation._debugger import WindowsDebugger
from os_access import RemotePath
from os_access import WindowsAccess
from os_access import copy_file
from os_access.windows_graphic_app import start_in_graphic_mode


class WindowsMobileClient(BaseInstallation):

    def __init__(self, os_access: WindowsAccess):
        super().__init__(os_access, os_access.home() / 'mobile_client')
        self.os_access = cast(WindowsAccess, self.os_access)
        self._local_app_data = self.os_access.home() / 'AppData' / 'Local'
        self._config_file = self._local_app_data / 'nx_ini' / 'mobile_client.ini'
        self.testkit_port = 7012
        self._log_dir = self._local_app_data / 'Network Optix' / 'Network Optix HD Witness Mobile Client' / 'log'
        self._debugger = WindowsDebugger(self.os_access)

    def get_binary_path(self) -> RemotePath:
        return self.dir / 'mobile_client.exe'

    def install(self, installer: RemotePath):
        self.os_access.unzip(installer, self.dir)
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def is_valid(self):
        return self.get_binary_path().exists()

    def _initialize_testkit(self):
        self._update_ini(f'clientWebServerPort={self.testkit_port}')

    def _update_ini(self, content: str):
        all_contents = []
        if self._config_file.exists():
            for line in self._config_file.read_text().splitlines():
                if content not in line:
                    all_contents.append(line)
        else:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
        all_contents.append(content)
        self._config_file.write_text('\n'.join(all_contents))

    def _connect_testkit(self, timeout: float = 20, testkit_port: int = 7012) -> TestKit:
        _logger.info('Connect to TestKit')
        testkit = TestKit(self.os_access.address, testkit_port)
        testkit.connect(timeout)
        testkit.reset_cache()
        return testkit

    def collect_artifacts(self, artifacts_path: Path):
        for file in self._log_dir.glob('*'):
            copy_file(file, artifacts_path / file.name)
        if len(self._list_core_dumps()) != 0:
            self._parse_core_dumps(artifacts_path)

    def _list_core_dumps(self) -> List[RemotePath]:
        return self._local_app_data.glob('*.dmp')

    def _parse_core_dumps(self, artifactory_dir):
        for core_dump in self._list_core_dumps():
            _logger.info('Parsing of dump %s started', core_dump)
            parsed_dump_name = core_dump.name + '.backtrace.txt'
            traceback_file = artifactory_dir / parsed_dump_name
            try:
                traceback = self._debugger.parse_core_dump(core_dump)
                traceback_file.write_bytes(traceback)
                _logger.info('Parsing of dump %s finished', core_dump)
            except Exception:
                _logger.exception('Cannot parse core dump: %s', core_dump)

    def configure_for_tests(self):
        log_level = 'verbose'
        self._update_ini(
            'enableLog=1\n'
            f'logFile={str(self._log_dir / log_level)}\n'
            f'logLevel={log_level}\n')

    def uninstall_all(self):
        with suppress(FileNotFoundError):
            self.dir.parent.rmtree()

    def start(self) -> Tuple[TestKit, HID]:
        self.configure_for_tests()
        self._initialize_testkit()
        self.os_access.run([
            'netsh',
            'advfirewall',
            'firewall',
            'add',
            'rule',
            'name=mobile_client.exe',
            'dir=in',
            'action=allow',
            f'program={str(self.get_binary_path())}',
            'enable=yes',
            'profile=any',
            ])
        _logger.info("Start Mobile Application")
        start_in_graphic_mode(self.os_access, [str(self.get_binary_path())])
        _logger.debug("Mobile Application started")
        testkit_api = self._connect_testkit(
            timeout=60,
            testkit_port=self.os_access.get_port('tcp', self.testkit_port),
            )
        hid = HID(testkit_api)
        MainWindow(testkit_api).set_position(350, 50)
        return testkit_api, hid


_logger = logging.getLogger(__name__)
