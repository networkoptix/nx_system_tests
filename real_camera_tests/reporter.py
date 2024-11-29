# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from typing import Mapping

from directories import run_metadata
from distrib import Version
from real_camera_tests.checks import Result


class CheckResults:

    def __init__(self):
        self._result = {}

    def store_run_info(self, run_vms_url: str, artifacts_url: str, **kwargs):
        self._result['run_info'] = {
            'run_vms_url': run_vms_url,
            'artifacts_url': artifacts_url,
            **kwargs,
            }

    def update_result(self, device_name, stage_name, result: Result, **kwargs):
        device_results = self._result.setdefault(device_name, {})
        device_results[stage_name] = device_results.setdefault(stage_name, {})
        device_results[stage_name] = {**device_results[stage_name], **result.as_dict(), **kwargs}

    def save_result(self, rct_reporter: '_RctReporter'):
        rct_reporter.save(self._result)


class _RctReporter(metaclass=ABCMeta):

    @abstractmethod
    def save(self, result: Mapping):
        pass


class RctLocalReporter(_RctReporter):

    def __init__(self, outfile: Path):
        self._outfile = outfile

    def save(self, result: Mapping):
        to_save = json.dumps(
            result,
            indent=4,
            )
        self._outfile.write_text(to_save)


class RctElasticReporter(_RctReporter):

    def __init__(self, elasticsearch, mediaserver_version: Version):
        self._elasticsearch = elasticsearch
        self._version = mediaserver_version

    def save(self, result: Mapping):
        for device, stages in result.items():
            self._elasticsearch.send_flush('ft-rct-{YYYY}', {
                'device': device,
                'stages': stages,
                'vms': self._version.as_str,
                **run_metadata(),
                })
