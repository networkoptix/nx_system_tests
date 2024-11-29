# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import string
from pathlib import Path
from pathlib import PurePosixPath
from typing import Collection

from provisioning import Command
from provisioning import CompositeCommand
from provisioning import Run
from provisioning.fleet import Fleet
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import PrepareVenv
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def provision(config: 'ProvisionConfiguration'):
    print(f"Service: {config.id()!r}")
    print(f"Fleet: {config.fleet_name()!r}")
    action = get_user_choice("Action", ['deploy', 'clean-up', 'start-after-failure'])
    if action == 'deploy':
        config.deploy()
    elif action == 'start-after-failure':
        config.start_after_failure()
    elif action == 'clean-up':
        print(
            f"WARNING: Service {config.id()!r} will be STOPPED "
            "and all service files will be DELETED. Are you sure?")
        confirmation = get_user_choice("Confirm", ['yes', 'no'])
        if confirmation == 'no':
            return
        config.clean_up()
    else:
        raise RuntimeError("Unexpected command")


class ProvisionConfiguration:

    def __init__(
            self,
            service_id: str,
            fleet: Fleet,
            deploy: Command,
            cleanup: Command,
            start_after_failure: Command,
            ):
        self._id = service_id
        self._fleet = fleet
        self._deploy = deploy
        self._cleanup = cleanup
        self._start_after_failure = start_after_failure

    def id(self) -> str:
        return self._id

    def fleet_name(self):
        return self._fleet.name()

    def deploy(self):
        self._fleet.run([self._deploy])

    def clean_up(self):
        self._fleet.run([self._cleanup])

    def start_after_failure(self):
        self._fleet.run([self._start_after_failure])


class SimpleServiceConfiguration(ProvisionConfiguration):

    def __init__(self, fleet: Fleet, service_file: Path):
        if not service_file.exists():
            raise RuntimeError(f"Unit file {service_file} does not exist")
        repo_dir = PurePosixPath(f'~ft/{service_file.stem}/ft')
        super().__init__(
            service_file.name,
            fleet,
            deploy=CompositeCommand([
                FetchRepo('ft', str(repo_dir)),
                PrepareVenv('ft', str(repo_dir), 'infrastructure'),
                LaunchSimpleSystemdService('ft', service_file),
                ]),
            cleanup=CompositeCommand([
                SystemCtl('ft', 'stop', service_file.name),
                SystemCtl('ft', 'disable', service_file.name),
                Run(f'sudo -u ft rm -rf {repo_dir.parent}'),
                Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{service_file.name}'),
                ]),
            start_after_failure=SystemCtl('ft', 'start', service_file.name),
            )


class MultiProcessServiceConfiguration(ProvisionConfiguration):
    """Manage multiprocess systemd service.

    There are two systemd unit files:
    - service unit of the actual service that executes some meaningful command;
    - target unit of the target service with Upholds= directive.
    Actual service processes exit on completion. They are restarted by a target service.
    On target service stop upheld services will complete their jobs, exits and will
    never be restarted again. This gives simple management of the multiple systemd services.
    """

    def __init__(self, fleet: Fleet, target_file: Path, service_file: Path):
        if not service_file.exists():
            raise RuntimeError(f"Unit file {service_file} does not exist")
        if not target_file.exists():
            raise RuntimeError(f"Unit file {target_file} does not exist")
        repo_dir = PurePosixPath(f'~ft/{service_file.stem}/ft')
        super().__init__(
            target_file.name,
            fleet,
            deploy=CompositeCommand([
                FetchRepo('ft', str(repo_dir)),
                PrepareVenv('ft', str(repo_dir), 'infrastructure'),
                UploadSystemdFile('ft', service_file),
                SystemCtl('ft', 'daemon-reload'),
                LaunchSimpleSystemdService('ft', target_file),
                ]),
            cleanup=CompositeCommand([
                SystemCtl('ft', 'stop', target_file.name),
                SystemCtl('ft', 'disable', target_file.name),
                Run(f'sudo -u ft rm -rf {repo_dir.parent}'),
                Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{target_file.name}'),
                Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{service_file.name}'),
                ]),
            start_after_failure=SystemCtl('ft', 'start', target_file.name),
            )


def get_user_choice(choice_name: str, allowed_values: Collection[str]):
    options = []
    shortcuts = {}
    for option in allowed_values:
        for c in option:
            if c in shortcuts:
                continue
            if c not in string.ascii_letters:
                continue
            shortcuts[c.casefold()] = option
            options.append(option.replace(c, f'[{c}]', 1))
            break
        else:
            options.append(option)
    options = ', '.join(options)
    while True:
        print(f"{choice_name} ({options} or Ctrl+D to exit): ", end='')
        try:
            choice = input()
        except EOFError:
            print("No choice, exiting")
            exit()
        choice = shortcuts.get(choice, choice)
        if choice in allowed_values:
            break
        else:
            print("Invalid input, please enter one of the options")
    return choice
