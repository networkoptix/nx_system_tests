# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools
import logging
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from typing import Mapping
from typing import Sequence

from directories.filelocker import AlreadyLocked
from directories.filelocker import FileLockDirectory
from vm.virtual_box._vboxmanage import get_vbox_user


def get_port_forwarding_table(raw_dict: Mapping[str, str]) -> Sequence['_ForwardedPort']:
    entries = []
    for index in itertools.count():  # Arbitrary.
        try:
            key = 'Forwarding({})'.format(index)
            entry = _ForwardedPort.from_conf(raw_dict[key])
            entries.append(entry)
        except KeyError:
            break
    return entries


class AccessSettings(metaclass=ABCMeta):

    @abstractmethod
    def claimed_port_range(self) -> AbstractContextManager[tuple[int, Sequence[str]]]:
        pass


class VBoxAccessSettings(AccessSettings):
    """Setup VirtualBox VM network access.

    >>> from pprint import pprint
    >>> a = VBoxAccessSettings({'tcp': {2: 22, 1: 7001}, 'udp': {5: 5353}})
    >>> pprint(a._modifyvm_params(20030))
    ['--natpf1',
     'tcp/22,tcp,,20032,,22',
     '--natpf1',
     'tcp/7001,tcp,,20031,,7001',
     '--natpf1',
     'udp/5353,udp,,20035,,5353',
     '--vrde',
     'on',
     '--vrdeport',
     '20030']
    """

    def __init__(
            self,
            guest_ports: Mapping[Literal['tcp', 'udp'], Mapping[int, int]],
            ):
        self._base = 10000
        self._per_vm = 10
        self._per_user = 100
        self._guest_ports = guest_ports
        for proto in 'tcp', 'udp':
            if guest_ports := guest_ports.get(proto, {}):
                if not (1 <= min(guest_ports) and max(guest_ports) < self._per_vm):
                    raise RuntimeError(
                        f"{proto} ports {guest_ports} don't fit into the range 1:{self._per_vm}")

    @contextmanager
    def claimed_port_range(self):
        user = get_vbox_user()
        if user.startswith('ft-'):
            user_base = int(user.lstrip('ft-')) * self._per_user
            vm_indices = range(user_base, user_base + self._per_user, self._per_vm)
        else:
            vm_indices = range(self._base, self._base + self._per_user * 100, self._per_vm)
        for vm_index in vm_indices:
            try:
                with _log_registry.try_locked(str(vm_index)):
                    yield vm_index, self._modifyvm_params(vm_index)
                    break
            except AlreadyLocked:
                pass
        else:
            raise RuntimeError(f"No available port ranges left for user {user!r}")

    def _modifyvm_params(self, vm_index) -> Sequence[str]:
        host_ports = range(vm_index, vm_index + self._per_vm)
        setup_access_command = []
        for protocol, port_map in self._guest_ports.items():
            for hint, guest_port in port_map.items():
                forwarded_port = _ForwardedPort.new(protocol, guest_port, host_ports[hint])
                setup_access_command.extend(('--natpf1', forwarded_port.conf()))
        rdp_port = host_ports[0]
        setup_access_command.extend(('--vrde', 'on', '--vrdeport', str(rdp_port)))
        return setup_access_command


class _ForwardedPort:

    def __init__(
            self,
            tag: str,
            protocol: Literal['tcp', 'udp'],
            host_address: str,
            host_port: int,
            guest_address: str,
            guest_port: int):
        self._tag = tag
        self.protocol = protocol
        self.host_address = host_address
        self.host_port = host_port
        self.guest_address = guest_address
        self.guest_port = guest_port

    def __repr__(self):
        return '<{} {}/{} to {}>'.format(
            self.__class__.__name__, self.protocol, self.guest_port, self.host_port)

    @classmethod
    def new(cls, protocol: Literal['tcp', 'udp'], guest_port: int, host_port: int):
        tag = '{}/{}'.format(protocol, guest_port)
        return cls(tag, protocol, '', host_port, '', guest_port)

    @classmethod
    def from_conf(cls, conf: str):
        tag, protocol, host_address, host_port_str, guest_address, guest_port_str = conf.split(',')
        return cls(
            tag, protocol,
            host_address, int(host_port_str),
            guest_address, int(guest_port_str))

    def conf(self) -> str:
        return ','.join((
            self._tag, self.protocol,
            self.host_address, str(self.host_port),
            self.guest_address, str(self.guest_port)))


_logger = logging.getLogger(__name__)
_log_registry = FileLockDirectory(Path('~/.cache/nx-func-tests/vm-locks').expanduser())
