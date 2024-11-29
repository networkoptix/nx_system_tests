# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import shlex
import subprocess
import sys
from string import Formatter
from types import MappingProxyType
from typing import Mapping
from typing import Sequence

from config import global_config


def main(args: Sequence[str]) -> int:
    # Tests that are run directly from GitLab (only Cloud Portal tests at the
    # time of writing) may only report their status via the exit code. Usually
    # tests exit with 0 if they exited correctly even if they indicated a
    # failure. Force a special exit code for this case.
    os.environ['FAILURE_EXIT_CODE'] = '10'
    script_commands = {
        'code_linter': '-m linter.run_linter',
        'doctest': '-m make_venv -m linter.run_doctest',
        'message_linter': '-m linter.run_git_lint {FT_COMMIT}',
        'unittest': '-m make_venv -m linter.run_unittest',
        'doc_generation': '-m linter.generate_doc',
        'ssh_job_dry_run': '-m run_ssh_job dry_run',
        'server_tests': '-m make_venv -m runner.run_batch --tag gitlab --installers-url {DISTRIB_URL}',
        'desktop_client_tests': '-m make_venv -m runner.run_batch --tag gui-smoke-test --installers-url {DISTRIB_URL}',
        'mobile_client_tests': '-m make_venv -m runner.run_batch --tag mobile-gitlab --installers-url {DISTRIB_URL}',
        'web_admin_tests': '-m make_venv -m runner.run_batch --tag web-admin-gitlab --webadmin-url {WEB_ADMIN_URL} --installers-url {DISTRIB_URL}',
        'cloud_portal_tests': '-m make_venv -m runner.run_batch --tag cloud_portal_gitlab --installers-url {DISTRIB_URL} --test-cloud-host {CLOUD_HOST} --cloud-state {CLOUD_STATE}',
        'server_snapshot_ubuntu18': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name ubuntu18 --installers-url {DISTRIB_URL}',
        'server_snapshot_ubuntu20': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name ubuntu20 --installers-url {DISTRIB_URL}',
        'server_snapshot_ubuntu22': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name ubuntu22 --installers-url {DISTRIB_URL}',
        'server_snapshot_ubuntu24': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name ubuntu24 --installers-url {DISTRIB_URL}',
        'server_snapshot_win10': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name win10 --installers-url {DISTRIB_URL}',
        'server_snapshot_win11': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name win11 --installers-url {DISTRIB_URL}',
        'server_snapshot_win2019': '-m make_venv -m vm.nxwitness_snapshots.mediaserver_plugin --os-name win2019 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi4_raspbian10_32': '-m make_venv -m arm_tests.install_mediaserver --model raspberry4 --arch x32 --os raspbian10 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi4_raspbian11_32': '-m make_venv -m arm_tests.install_mediaserver --model raspberry4 --arch x32 --os raspbian11 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi4_raspbian11_64': '-m make_venv -m arm_tests.install_mediaserver --model raspberry4 --arch x64 --os raspbian11 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi4_raspbian12_32': '-m make_venv -m arm_tests.install_mediaserver --model raspberry4 --arch x32 --os raspbian12 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi4_raspbian12_64': '-m make_venv -m arm_tests.install_mediaserver --model raspberry4 --arch x64 --os raspbian12 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi5_raspbian12_32': '-m make_venv -m arm_tests.install_mediaserver --model raspberry5 --arch x32 --os raspbian12 --installers-url {DISTRIB_URL}',
        'server_snapshot_rpi5_raspbian12_64': '-m make_venv -m arm_tests.install_mediaserver --model raspberry5 --arch x64 --os raspbian12 --installers-url {DISTRIB_URL}',
        'server_snapshot_jetsonnano_ubuntu18_64': '-m make_venv -m arm_tests.install_mediaserver --model jetsonnano --arch x64 --os ubuntu18 --installers-url {DISTRIB_URL}',
        'server_snapshot_orinnano_ubuntu22_64': '-m make_venv -m arm_tests.install_mediaserver --model orin_nano --arch x64 --os ubuntu22 --installers-url {DISTRIB_URL}',
        'desktop_client_installation_ubuntu18': '-m make_venv -m installation.install_client --os-name ubuntu18 --installers-url {DISTRIB_URL}',
        'desktop_client_installation_ubuntu20': '-m make_venv -m installation.install_client --os-name ubuntu20 --installers-url {DISTRIB_URL}',
        'desktop_client_installation_ubuntu22': '-m make_venv -m installation.install_client --os-name ubuntu22 --installers-url {DISTRIB_URL}',
        'desktop_client_installation_ubuntu24': '-m make_venv -m installation.install_client --os-name ubuntu24 --installers-url {DISTRIB_URL}',
        'desktop_client_installation_win11': '-m make_venv -m installation.install_client --os-name win11 --installers-url {DISTRIB_URL}',
        'desktop_client_snapshot_win10': '-m make_venv -m vm.nxwitness_snapshots.client_plugin --os-name win10 --installers-url {DISTRIB_URL}',
        'desktop_client_snapshot_win11': '-m make_venv -m vm.nxwitness_snapshots.client_plugin --os-name win11 --installers-url {DISTRIB_URL}',
        'desktop_client_snapshot_rpi4_raspbian12_64': '-m make_venv -m arm_tests.install_client --model raspberry4 --arch x64 --os raspbian12 --installers-url {DISTRIB_URL}',
        'desktop_client_snapshot_rpi5_raspbian12_64': '-m make_venv -m arm_tests.install_client --model raspberry5 --arch x64 --os raspbian12 --installers-url {DISTRIB_URL}',
        'bundle_installation_win11': '-m make_venv -m installation.install_bundle --os-name win11 --installers-url {DISTRIB_URL}',
        'bundle_snapshot_win10': '-m make_venv -m vm.nxwitness_snapshots.bundle_plugin --os-name win10 --installers-url {DISTRIB_URL}',
        'bundle_snapshot_win11': '-m make_venv -m vm.nxwitness_snapshots.bundle_plugin --os-name win11 --installers-url {DISTRIB_URL}',
        }
    [script] = args
    if script == 'dry_run':
        os.environ['DRY_RUN'] = 'true'
        dry_run_args = {
            'DISTRIB_URL': 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/master/12345/default/distrib/',
            'CLOUD_HOST': global_config['test_cloud_host'],
            'ARTIFACTORY_WEBADMIN_URL': 'https://example.com/artifactory/build-webadmin-gitlab/5ca1ab1edeadc0de5ca1ab1edeadc0dedeadc0de/',
            'CLOUD_STATE': 'https://example.com/foo/bar',
            'FT_COMMIT': os.getenv('CI_COMMIT_SHA', 'HEAD'),
            'WEB_ADMIN_URL': 'builtin:',
            }
        exit_codes = []
        for command_template in script_commands.values():
            exit_codes.append(_Command(command_template).run(defaults=dry_run_args))
        return 10 if any(code != 0 for code in exit_codes) else 0
    else:
        # Support deprecated names until all pipelines adopt the new ones.
        command_synonyms = {
            'snapshots_mediaserver_ubuntu18': 'server_snapshot_ubuntu18',
            'snapshots_mediaserver_ubuntu20': 'server_snapshot_ubuntu20',
            'snapshots_mediaserver_ubuntu22': 'server_snapshot_ubuntu22',
            'snapshots_mediaserver_ubuntu24': 'server_snapshot_ubuntu24',
            'snapshots_mediaserver_win10': 'server_snapshot_win10',
            'snapshots_mediaserver_win11': 'server_snapshot_win11',
            'snapshots_mediaserver_win2019': 'server_snapshot_win2019',
            'install_client_ubuntu18': 'desktop_client_installation_ubuntu18',
            'install_client_ubuntu20': 'desktop_client_installation_ubuntu20',
            'install_client_ubuntu22': 'desktop_client_installation_ubuntu22',
            'install_client_ubuntu24': 'desktop_client_installation_ubuntu24',
            'install_client_win11': 'desktop_client_installation_win11',
            'install_bundle_win11': 'bundle_installation_win11',
            'snapshots_client_win10': 'desktop_client_snapshot_win10',
            'snapshots_client_win11': 'desktop_client_snapshot_win11',
            'snapshots_bundle_win10': 'bundle_snapshot_win10',
            'snapshots_bundle_win11': 'bundle_snapshot_win11',
            'snapshots_mediaserver_rpi4_raspbian10_32': 'server_snapshot_rpi4_raspbian10_32',
            'snapshots_mediaserver_rpi4_raspbian11_32': 'server_snapshot_rpi4_raspbian11_32',
            'snapshots_mediaserver_rpi4_raspbian11_64': 'server_snapshot_rpi4_raspbian11_64',
            'snapshots_mediaserver_rpi4_raspbian12_32': 'server_snapshot_rpi4_raspbian12_32',
            'snapshots_mediaserver_rpi4_raspbian12_64': 'server_snapshot_rpi4_raspbian12_64',
            'snapshots_mediaserver_rpi5_raspbian12_32': 'server_snapshot_rpi5_raspbian12_32',
            'snapshots_mediaserver_rpi5_raspbian12_64': 'server_snapshot_rpi5_raspbian12_64',
            'snapshots_mediaserver_jetsonnano_ubuntu18_64': 'server_snapshot_jetsonnano_ubuntu18_64',
            'snapshots_mediaserver_orinnano_ubuntu22_64': 'server_snapshot_orinnano_ubuntu22_64',
            'snapshots_client_rpi4_raspbian12_64': 'desktop_client_snapshot_rpi4_raspbian12_64',
            'snapshots_client_rpi5_raspbian12_64': 'desktop_client_snapshot_rpi5_raspbian12_64',
            }
        [command_name, *positional_args] = shlex.split(os.path.expandvars(script))
        command = _Command(script_commands[command_synonyms.get(command_name, command_name)])
        return command.run(positional_args)


class _Command:

    def __init__(self, template: str):
        self._template = template
        self._formatter = Formatter()

    def run(
            self,
            args: Sequence[str] = (),
            defaults: Mapping[str, str] = MappingProxyType({}),
            ) -> int:
        kwargs = dict(zip(self._placeholders(), args))
        command = self._formatter.format(self._template, **defaults, **kwargs)
        return _run(command)

    def _placeholders(self) -> Sequence[str]:
        return [p[1] for p in self._formatter.parse(self._template)]


def _run(command: str):
    command = shlex.quote(sys.executable) + ' ' + command  # For printing
    print(f"===== Run: {command} =====", flush=True)
    p = subprocess.run(shlex.split(command))
    print(f"===== Exit code {p.returncode}: {command} =====", flush=True)
    return p.returncode


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
