# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from datetime import datetime
from datetime import timezone
from typing import Mapping
from urllib.parse import quote_plus

from directories import make_artifact_store
from infrastructure._message_broker_config import get_default_client


class Reporter:

    def __init__(self, url: str):
        self._repr = f'{self.__class__.__name__}({url!r})'
        self._base_url = url
        self._run_url = None

    def __enter__(self):
        self._client = get_default_client()
        self._updates_output = self._client.get_producer('ft:run_updates')
        return self

    def __repr__(self):
        return self._repr

    def send(self, stage_data: Mapping[str, str]) -> str:
        _logger.info("Stage update: %r", stage_data)
        self._updates_output.write_message(json.dumps(stage_data))
        # TODO: Consider asking FT View for the run URL.
        started_at = stage_data['run_started_at_iso']
        started_at = datetime.fromisoformat(started_at)
        started_at = started_at.astimezone(timezone.utc)
        started_at = started_at.replace(tzinfo=None)
        started_at = started_at.isoformat('T', 'microseconds')
        run_url = '/'.join((
            self._base_url,
            'runs',
            quote_plus(stage_data['run_username']),
            quote_plus(stage_data['run_hostname']),
            started_at,
            ))
        if self._run_url is None or run_url != self._run_url:
            self._run_url = run_url
            _logger.info("Start reporting to FT View URL: %s", self._run_url)
        return run_url

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self._updates_output
        self._client.close()
        del self._client


class StageReporter:

    def __init__(self, reporter: Reporter, run_dir, run_properties):
        self._reporter = reporter
        self._run_dir = run_dir
        self._run_properties = run_properties
        required_properties = {
            'run_username',
            'run_hostname',
            'run_started_at_iso',
            'run_pid',
            'run_cmdline',
            }
        if not required_properties.issubset(set(run_properties.keys())):
            raise RuntimeError(f"Missing fields in run properties: {required_properties - set(run_properties.keys())}")

    def __enter__(self):
        self._reporter = self._reporter.__enter__()
        self._artifact_store = make_artifact_store()
        self._started_at = time.monotonic()
        self._run_url = self._reporter.send({
            **self._run_properties,
            'stage_status': 'running',
            'artifact_urls': self._artifact_store.store_new(self._run_dir),
            })
        return self

    def get_run_url(self) -> str:
        return self._run_url

    def set_passed(self):
        return self._reporter.send({
            **self._run_properties,
            'stage_status': 'passed',
            'stage_duration_sec': time.monotonic() - self._started_at,
            'artifact_urls': self._artifact_store.store_new(self._run_dir),
            })

    def set_failed(self, message: str):
        return self._reporter.send({
            **self._run_properties,
            'stage_status': 'failed',
            'stage_message': message,
            'stage_duration_sec': time.monotonic() - self._started_at,
            'artifact_urls': self._artifact_store.store_new(self._run_dir),
            })

    def set_skipped(self, message: str):
        return self._reporter.send({
            **self._run_properties,
            'stage_status': 'skipped',
            'stage_message': message,
            'stage_duration_sec': time.monotonic() - self._started_at,
            'artifact_urls': self._artifact_store.store_new(self._run_dir),
            })

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._reporter.__exit__(exc_type, exc_val, exc_tb)


_logger = logging.getLogger(__name__)
