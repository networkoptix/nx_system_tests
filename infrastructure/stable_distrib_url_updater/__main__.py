# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
import sys
from typing import Sequence

from _internal.service_registry import gitlab_dev_nx
from _internal.service_registry import vms_build_registry
from infrastructure._logging import init_logging
from infrastructure._uri import get_process_uri


def main(args: Sequence[str]) -> int:
    parsed_args = _parse_args(args)
    sha = _get_vms_stable_sha(parsed_args.branch)
    records = vms_build_registry.list_builds_by_sha(sha)
    if not records:
        _logger.error("No build records found for commit %s", sha)
        return 2
    stable_records = [record for record in records if record.build_is_stable()]
    if not stable_records:
        [latest_build_record, *_] = records
        _logger.info("Mark record as VMS stable: %s", latest_build_record.raw())
        stable_build_record = latest_build_record.with_stable_mark()
        vms_build_registry.add_record(stable_build_record.raw())
    else:
        [stable_build_record, *_] = stable_records
        _logger.info(
            "Stable distrib URL did not change since last run: %s",
            stable_build_record.distrib_url())
    return 0


def _get_vms_stable_sha(branch: str) -> str:
    succeeded_pipelines = gitlab_dev_nx.list_recently_succeeded_pipelines(branch)
    stage = 'ft (#ask-ft)'
    for pipeline in succeeded_pipelines:
        ft_latest_attempts = [
            attempts[-1]
            for attempts in pipeline.list_job_attempts().values()
            if attempts[-1].stage() == 'ft (#ask-ft)'
            ]
        if not ft_latest_attempts:
            _logger.warning(f"Job stage {stage!r} not found in pipeline {pipeline}")
            continue
        if any(a.status() != 'success' for a in ft_latest_attempts):
            _logger.debug("Some jobs failed in %s", pipeline)
            continue
        _logger.info("Succeeded pipeline: %s", pipeline)
        sha = pipeline.sha()
        break
    else:
        raise RuntimeError(f"Failed to find succeeded pipeline for {branch}")
    return sha


def _parse_args(args: Sequence[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'branch',
        help="VMS branch to search installers URL and run tests.",
        )
    return parser.parse_args(args)


_logger = logging.getLogger()


if __name__ == '__main__':
    init_logging(get_process_uri())
    exit(main(sys.argv[1:]))
