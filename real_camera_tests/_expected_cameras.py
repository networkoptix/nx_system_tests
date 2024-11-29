# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import importlib.util
import logging
import re
from pathlib import Path

from real_camera_tests.camera_stage import GenericLinkConfig
from real_camera_tests.camera_stage import NvrAnotherChannelConfig
from real_camera_tests.camera_stage import NvrFirstChannelConfig
from real_camera_tests.camera_stage import SingleRealCameraConfig
from real_camera_tests.server_stage import ServerConfig

_logger = logging.getLogger(__name__)

expected_cameras_parent = Path(__file__).parent.joinpath('expected_cameras')


class ExpectedCameras:

    def __init__(self, dir, camera_filter_re=re.compile('.*')):
        self._all_configs = []
        for file in dir.iterdir():
            if file.suffix != '.py':
                continue
            spec = importlib.util.spec_from_file_location(file.stem, str(file))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            config = module.config
            if isinstance(config, ServerConfig):
                self.server_config = config
            else:
                self._all_configs.append(config)
        self.filtered_camera_configs = []
        self.skipped_camera_configs = []
        self.generic_link_configs = []
        self.nvr_physical_ids = []
        self.camera_count_metric = 0
        for config in self._all_configs:
            if camera_filter_re.fullmatch(config.name) is None:
                self.skipped_camera_configs.append(config)
                continue
            if isinstance(config, GenericLinkConfig):
                self.generic_link_configs.append(config)
                self.camera_count_metric += 1
            if isinstance(config, NvrFirstChannelConfig):
                self.nvr_physical_ids.append(config.physical_id)
                self.camera_count_metric += config.channel_count
            if isinstance(config, SingleRealCameraConfig):
                self.camera_count_metric += 1
            self.filtered_camera_configs.append(config)
        self.filtered_camera_count = len(self.filtered_camera_configs)
        try:
            server_config = self.server_config
        except AttributeError:
            pass
        else:
            server_config.set_offline_statuses_limit_after(self.filtered_camera_count)
        self.physical_ids_auto = self._get_expected_cameras_physical_ids(is_auto=True)
        self.physical_ids_manual = self._get_expected_cameras_physical_ids(is_auto=False)

    def _get_expected_cameras_physical_ids(self, is_auto=True):
        expected_cameras = []
        for config in self._all_configs:
            if isinstance(config, NvrAnotherChannelConfig):
                _logger.debug(
                    "%s: Not main channel of multichannel device, channel id are generated",
                    config.name)
                continue
            if is_auto:
                if config.physical_id.auto is None:
                    _logger.debug("%s: Can only be added manually", config.name)
                    continue
                physical_id = config.physical_id.auto
            else:
                physical_id = config.physical_id.manual
            _logger.debug(
                "%s: physical_id %s is used for %s discovery",
                config.name, physical_id, 'auto' if is_auto else 'manual')
            expected_cameras.append(physical_id)
            if isinstance(config, NvrFirstChannelConfig):
                channel_count = config.channel_count
                expected_cameras.extend(
                    [f'{physical_id}_channel={n}' for n in range(2, channel_count + 1)])
        return expected_cameras
