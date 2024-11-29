# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import os
import shlex
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from typing import Sequence

from config import global_config


def main(args: Sequence[str]) -> int:
    main_parser = argparse.ArgumentParser()
    job_parsers = []
    job_parser = main_parser.add_subparsers(dest='job', required=True)
    job_parser.add_parser('dry_run', help="Dry run all known jobs. Use to debug the script.")
    job_parsers.append(job_parser.add_parser('test_cloud', help="Run cloud tests against specific cloud host"))
    job_parsers[-1].set_defaults(
        command=(
            '-m make_venv -m runner.run_batch --tag cloud_portal_smoke '
            '--test-cloud-host {CLOUD_HOST} --installers-url {INSTALLERS_URL} --cloud-state {CLOUD_STATE}'))
    _add_cloud_host_argument(job_parsers[-1])
    _add_installers_url_argument(job_parsers[-1])
    _add_cloud_state_argument(job_parsers[-1])
    job_parsers.append(job_parser.add_parser('test_cloud_prod', help="Run cloud tests against production cloud host"))
    job_parsers[-1].set_defaults(
        command=(
            '-m make_venv -m runner.run_batch --tag cloud_portal_gitlab '
            '--test-cloud-host nxvms.com --installers-url {INSTALLERS_URL} --cloud-state {CLOUD_STATE}'))
    _add_installers_url_argument(job_parsers[-1])
    _add_cloud_state_argument(job_parsers[-1])
    parsed_args = main_parser.parse_args(args)
    if parsed_args.job == 'dry_run':
        os.environ['DRY_RUN'] = 'true'
        dry_run_defaults = {
            'CLOUD_HOST': global_config['test_cloud_host'],
            'CLOUD_STATE': 'at:' + datetime.now(timezone.utc).isoformat(timespec='microseconds'),
            'INSTALLERS_URL': 'branch:master',
            }
        exit_codes = []
        for parser in job_parsers:
            command = parser.get_default('command').format(**dry_run_defaults)
            exit_code = _run(command)
            exit_codes.append(exit_code)
        return 10 if any(code != 0 for code in exit_codes) else 0
    else:
        command = parsed_args.command.format(**dict(parsed_args._get_kwargs()))
        return _run(command)


def _add_cloud_host_argument(parser: argparse.ArgumentParser):
    parser.add_argument(
        'CLOUD_HOST',
        help="Cloud host name (e.g. test.ft-cloud.hdw.mx)")


def _add_installers_url_argument(parser: argparse.ArgumentParser):
    parser.add_argument(
        'INSTALLERS_URL',
        help="Installers URL pointed to a distrib folder or a branch name in a format branch:<branch_name>")


def _add_cloud_state_argument(parser: argparse.ArgumentParser):
    parser.add_argument(
        'CLOUD_STATE',
        nargs='?',
        default='at:' + datetime.now(timezone.utc).isoformat(timespec='microseconds'),
        help=(
            "An arbitrary string that helps to identify deployed cloud state. "
            "Re-run a job with the same arguments to only restart failed tests, if any. "
            "Re-run a job with a new state argument to run all tests on a given cloud host again."))


def _run(command) -> int:
    command = shlex.quote(sys.executable) + ' ' + command  # For printing
    print(f"===== Run: {command} =====", flush=True)
    p = subprocess.run(shlex.split(command))
    print(f"===== Exit code {p.returncode}: {command} =====", flush=True)
    return p.returncode


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
