# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import re
import shlex
import sys
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from pathlib import PurePosixPath
from typing import Collection
from typing import Sequence

from provisioning._ssh import ssh
from provisioning._ssh import ssh_input


class Command(metaclass=ABCMeta):

    @abstractmethod
    def run(self, host: str):
        pass


class Run(Command):

    def __init__(self, command):
        self._command = command

    def __repr__(self):
        return f'{Run.__name__}({self._command!r})'

    def run(self, host):
        ssh(host, self._command)


class Input(Command):

    def __init__(self, local_path: str, command: str):
        self._repr = f'{Input.__name__}({local_path!r}, {command!r})'
        path = Path(local_path).expanduser()
        self._local_path = Path(self._root, path)
        if not self._local_path.exists():
            raise ValueError(f"Does not exist: {self._local_path}")
        self._command = command

    def __repr__(self):
        return self._repr

    def run(self, host):
        ssh_input(host, self._command, self._local_path.read_bytes())

    _root = Path(__file__).parent.parent
    assert str(_root) in sys.path


class _Install(Input):
    """Upload file. Set permissions. Make dirs (-D is passed by default).

    >>> from pathlib import Path
    >>> print(Path(__file__).name)
    _core.py
    >>> print(_Install('ft', str(Path(__file__)), '~ft/q w/e/')._command)
    sudo install /dev/stdin ~ft/'q w/e/_core.py' -o ft -g ft -D
    >>> print(_Install('root', str(Path(__file__)), '/e/s/d/')._command)
    sudo install /dev/stdin /e/s/d/_core.py -o root -g root -D
    >>> _Install('root', str(Path(__file__)), '/e/s/d') # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    RuntimeError: Target must be a directory and ends with /, got '/e/s/d'
    """

    def __init__(self, user: str, local_path: str, target_dir: str, *params: str):
        if not target_dir.endswith('/'):
            raise RuntimeError(f"Target must be a directory and ends with /, got {target_dir!r}")
        target = PurePosixPath(target_dir, Path(local_path).name)
        target_quoted = self._quote_path(target)
        params_joined = shlex.join([*params, '-o', user, '-g', user, '-D'])
        command = f'sudo install /dev/stdin {target_quoted} {params_joined}'
        super().__init__(local_path, command)

    @staticmethod
    def _quote_path(target: PurePosixPath):
        if target.parts[0].startswith('~'):
            if shlex.quote(target.parts[0][1:]) == target.parts[0][1:]:
                return target.parts[0] + '/' + shlex.quote(str(PurePosixPath(*target.parts[1:])))
        return shlex.quote(str(target))


class InstallCommon(_Install):

    def __init__(self, user: str, local_path: str, target_dir: str):
        super().__init__(user, local_path, target_dir, '-m', 'u=rwX,go=rX')


class InstallSecret(_Install):

    def __init__(self, user: str, local_path: str, target_dir: str):
        super().__init__(user, local_path, target_dir, '-m', 'u=rwX,go=')


class CompositeCommand(Command):

    def __init__(self, commands: Sequence[Command]):
        self._commands: Sequence[Command] = commands

    def __repr__(self):
        return f'<{self.__class__.__name__} with {len(self._commands)} commands>'

    def run(self, host):
        for command in self._commands:
            command.run(host)


class Fleet:

    def __init__(self, hosts: Sequence[str]):
        self._hosts = hosts

    @staticmethod
    def compose(fleets: 'Sequence[Fleet]'):
        return Fleet([h for f in fleets for h in f._hosts])

    def run(self, commands: Sequence[Command]):
        for host in self._hosts:
            for command in commands:
                print(f"Command {command!r}")
                questionnaire = Questionnaire("Run on")
                if questionnaire.user_agrees_with(host):
                    command.run(host)

    def name(self):
        return _HostGroup(self._hosts).short_name()


class Questionnaire:

    def __init__(self, prompt):
        self._user_agrees = None
        self._should_ask_user = True
        self._prompt = prompt

    def user_agrees_with(self, question):
        if not os.getenv('PROVISIONING_ASK_FOR_CONFIRMATION', ''):
            return True
        prompt = f"{self._prompt} {question} [y,n,a,d]? "
        if self._should_ask_user:
            while True:
                answer = input(prompt)
                answer = answer[:1]
                answer = answer.lower()
                if answer == 'y':
                    self._user_agrees = True
                    self._should_ask_user = True
                elif answer == 'n':
                    self._user_agrees = False
                    self._should_ask_user = True
                elif answer == 'a':
                    self._user_agrees = True
                    self._should_ask_user = False
                elif answer == 'd':
                    self._user_agrees = False
                    self._should_ask_user = False
                else:
                    self._user_agrees = None
                if self._user_agrees is not None:
                    break
        else:
            assert self._user_agrees is not None
            answer = 'a' if self._user_agrees else 'd'
            print(prompt + answer, flush=True)
        return self._user_agrees


class _HostGroup:
    """Make short name for host group.

    >>> group = _HostGroup(['sc-ft001.nxlocal', 'sc-ft002.nxlocal', 'sc-ft003.nxlocal'])
    >>> group.short_name()
    'sc-ft{001..003}.nxlocal'
    >>> group = _HostGroup(['sc-ft001.nxlocal1', 'sc-ft002.nxlocal2', 'sc-ft003.nxlocal3'])
    >>> group.short_name()
    'sc-ft001.nxlocal1, sc-ft002.nxlocal2, sc-ft003.nxlocal3'
    >>> group = _HostGroup(['sca-ft001.nxlocal', 'scb-ft002.nxlocal', 'scc-ft003.nxlocal'])
    >>> group.short_name()
    'sca-ft001.nxlocal, scb-ft002.nxlocal, scc-ft003.nxlocal'
    >>> group = _HostGroup(['host1', 'host2', 'host4', 'host5'])
    >>> group.short_name()
    'host{1..2}, host{4..5}'
    """

    _name_re = re.compile(r'(?P<prefix>[a-zA-Z._-]+?)(?P<digits>\d+)(?P<suffix>[0-9a-zA-Z._-]*)')

    def __init__(self, hosts: Collection[str]):
        [first, *rest] = sorted(hosts)
        self._groups = [[first]]
        for host in rest:
            self._add_host(host)

    def short_name(self) -> str:
        return ', '.join([self._group_name(group) for group in self._groups])

    def _group_name(self, hosts: Sequence[str]):
        if len(hosts) == 0:
            return ''
        if len(hosts) == 1:
            return hosts[0]
        [first, *_, last] = hosts
        first_match = self._name_re.fullmatch(first)
        assert first_match is not None
        last_match = self._name_re.fullmatch(last)
        assert last_match is not None
        host_sequence = '{' + first_match['digits'] + '..' + last_match['digits'] + '}'
        return first_match['prefix'] + host_sequence + first_match['suffix']

    def _add_host(self, host: str):
        if not self._groups:
            self._groups.append([host])
            return
        if self._is_adjacent(self._groups[-1][-1], host):
            self._groups[-1].append(host)
        else:
            self._groups.append([host])

    def _is_adjacent(self, first: str, other: str) -> bool:
        first_match = self._name_re.fullmatch(first)
        other_match = self._name_re.fullmatch(other)
        if first_match is None or other_match is None:
            return False
        if first_match['prefix'] != other_match['prefix']:
            return False
        if first_match['suffix'] != other_match['suffix']:
            return False
        if int(first_match['digits']) + 1 != int(other_match['digits']):
            return False
        return True
