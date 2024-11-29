# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
import subprocess
import sys
import time
from collections.abc import Sequence
from typing import NamedTuple
from typing import Optional

from _internal.service_registry import vms_build_registry

TESTS = ['files', 'cpu_ram', 'rec_cameras', 'http_rtsp']


def main(args: Sequence[str]) -> int:
    parsed_args = parse_args(args)
    if parsed_args.branch:
        build_record = vms_build_registry.get_stable_build(parsed_args.branch)
        installers_url = build_record.distrib_url()
    else:
        installers_url = parsed_args.installers_url
    tests = [parsed_args.test] if parsed_args.test else TESTS
    run_tests = parsed_args.operation in ['all', 'tests']
    run_reports = parsed_args.operation in ['all', 'reports']
    report: list[RunStatus] = []
    if run_tests and 'files' in tests:
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_files.py',
            '--installers-url', installers_url,
            '--test-function', 'test_1800s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Files comparison test', return_code))
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_files.py',
            '--installers-url', installers_url,
            '--test-function', 'test_1800s_with_object_detection',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Files comparison test, with object detection', return_code))
    if run_reports and 'files' in tests:
        time.sleep(10)  # Elasticsearch needs some time to handle and store data from the tests.
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_files.py']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Files comparison report', return_code))
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_files.py', '--all-types']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Files comparison report, full', return_code))
    if run_tests and 'cpu_ram' in tests:
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_cpu_ram_usage.py',
            '--installers-url', installers_url,
            '--test-function', 'test_ubuntu22_1800s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('CPU/RAM comparison test, Ubuntu 22', return_code))
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_cpu_ram_usage.py',
            '--installers-url', installers_url,
            '--test-function', 'test_win11_1800s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('CPU/RAM comparison test, Windows 10', return_code))
    if run_reports and 'cpu_ram' in tests:
        time.sleep(10)  # Elasticsearch needs some time to handle and store data from the tests.
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_cpu_ram_usage.py']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('CPU/RAM comparison report', return_code))
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_cpu_ram_usage.py', '--all-types']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('CPU/RAM comparison report, full', return_code))
    if run_tests and 'rec_cameras' in tests:
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_maximum_recording_cameras.py',
            '--installers-url', installers_url,
            '--test-function', 'test_ubuntu22_3600s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Maximum recording cameras comparison test, Ubuntu 22', return_code))
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_maximum_recording_cameras.py',
            '--installers-url', installers_url,
            '--test-function', 'test_win11_3600s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Maximum recording cameras comparison test, Windows 10', return_code))
    if run_reports and 'rec_cameras' in tests:
        time.sleep(10)  # Elasticsearch needs some time to handle and store data from the tests.
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_maximum_recording_cameras.py']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Maximum recording cameras comparison report', return_code))
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_maximum_recording_cameras.py', '--all-types']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('Maximum recording cameras comparison report, full', return_code))
    if run_tests and 'http_rtsp' in tests:
        cmd = [
            '-m', 'make_venv',
            'long_tests/comparison_test_http_rtsp.py',
            '--installers-url', installers_url,
            '--test-function', 'test_4_cameras_1800s',
            ]
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('HTTP/RTSP requests comparison test', return_code))
    if run_reports and 'http_rtsp' in tests:
        time.sleep(10)  # Elasticsearch needs some time to handle and store data from the tests
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_http_rtsp.py']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('HTTP/RTSP requests comparison report', return_code))
        cmd = ['-m', 'make_venv', 'long_tests/comparison_report_http_rtsp.py', '--all-types']
        _logger.info("Run script: %s", cmd)
        return_code = subprocess.run([sys.executable, *cmd]).returncode
        report.append(RunStatus('HTTP/RTSP requests comparison report, full', return_code))
    _logger.info("\nComparison tests have finished")
    cmd = ['-m', 'make_venv', 'long_tests/comparison_data_export.py']
    _logger.info("Run script: %s", cmd)
    return_code = subprocess.run([sys.executable, *cmd]).returncode
    report.append(RunStatus('Export comparison results to Google Sheets', return_code))
    for line in report:
        _logger.info(f"{line.name.ljust(60)}, return code {line.return_code}")
    if all(line.return_code == 0 for line in report):
        return 0
    else:
        return 200


class RunStatus(NamedTuple):
    name: str
    return_code: int


def parse_args(arguments: Sequence[str]) -> Optional[argparse.Namespace]:
    parser = argparse.ArgumentParser()
    branch_or_installer_group = parser.add_mutually_exclusive_group(required=True)
    branch_or_installer_group.add_argument(
        '--branch',
        default=None,
        choices=['vms_6.0.1', 'vms_6.0_patch', 'master'],
        help="VMS branch from which installers URL will be chosen.",
        )
    branch_or_installer_group.add_argument(
        '--installers-url',
        default=None,
        help="Installer URL.",
        )
    parser.add_argument(
        '--test',
        required=False,
        choices=TESTS,
        help="Test name for run. If not specified, all tests will be run.",
        )
    parser.add_argument(
        '--operation',
        required=False,
        choices=['all', 'tests', 'reports'],
        default='all',
        help="VMS branch from which installers URL will be chosen.",
        )
    parsed = parser.parse_args(arguments)
    return parsed


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)7s %(message)s",
        )
    _logger = logging.getLogger('')
    exit(main(sys.argv[1:]))
