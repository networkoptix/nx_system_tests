# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import time
from typing import Collection
from uuid import UUID


class ClientStateDirectory:
    """Using for getting paths of configs or initial check of state directory structure."""

    def __init__(self, path):
        self._path = path
        self._manual_configs = []
        self._reload()

    def _reload(self):
        for content in self._path.glob("*"):
            if content.name == 'auto_state.json':
                self._general_auto_config = _StateConfig(content)
                continue
            elif content.is_dir():
                # In tests with 2 windows we will have an additional directory with name temp.
                # Now we don't check this.
                self._manual_configs.append(_StateDirectory(content).manual_config)

    def get_general_auto_config(self) -> '_StateConfig':
        return self._general_auto_config

    def list_manual_configs(self) -> Collection['_StateDirectory']:
        return self._manual_configs

    def wait_for_manual_configs_count(self, count: int) -> Collection['_StateDirectory']:
        start_time = time.monotonic()
        while True:
            if len(self._manual_configs) == count:
                return self._manual_configs
            if time.monotonic() - start_time > 1:
                raise RuntimeError(
                    f"Wrong manual configs count."
                    f"Expected {count}, got {len(self._manual_configs)}.")
            time.sleep(0.1)
            self._reload()


class _StateDirectory:

    def __init__(self, directory):
        self.manual_config = None
        self.auto_config = None
        for config_file in directory.glob("*"):
            if config_file.name == 'auto_state.json':
                self.auto_config = _StateConfig(config_file)
                # Currently, there are no tests that use user auto-configs.
                continue
            if config_file.suffix == ".json":
                if self.manual_config is not None:
                    raise RuntimeError(
                        "Currently, we check one manual .json file in user-specific directory.")
                self.manual_config = _StateConfig(config_file)
                continue
            raise RuntimeError("Unexpected file in user-specific directory.")
        if self.manual_config is None and self.auto_config is None:
            raise RuntimeError("Empty user-specific directory.")


class _StateConfig:
    """Provides general methods for working with configs and their parameters."""

    def __init__(self, path):
        self._path = path

    def _json_load(self) -> dict:
        data = self._path.read_bytes()
        file = json.loads(data)
        return file

    def is_full_screen(self) -> bool:
        return self._json_load()['windowGeometry']['geometry']['isFullscreen']

    def get_resource_browser_width(self) -> int:
        return self._json_load()['workbenchSettings']['Tree']['span']

    def _current_layout_uuid_version(self) -> int:
        current_layout_id = self._json_load()['workbenchState']['currentLayoutId']
        return UUID(current_layout_id).version

    def get_layout_id_format_verification(self) -> bool:
        """Layout id must be UUID object."""
        try:
            self._current_layout_uuid_version()
            return True
        except ValueError:
            return False
