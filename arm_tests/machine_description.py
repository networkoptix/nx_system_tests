# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import hashlib
import shlex
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class MachineDescription(metaclass=ABCMeta):

    @abstractmethod
    def make_request(self, *disk_stems: str) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def get_versioned_prerequisites(self, name: str) -> tuple[bytes, str]:
        pass


def get_machine_description(args: argparse.Namespace) -> MachineDescription:
    try:
        name = args.name
    except AttributeError:
        return _GenericMachine(args.model, args.arch, args.os)
    return _NamedMachine(args.model, args.arch, args.os, name)


class _ScriptDescribedMachine(MachineDescription, metaclass=ABCMeta):

    def __init__(self, model: str, arch: str, os: str):
        self._model = model
        self._arch = arch
        self._os = os

    def get_versioned_prerequisites(self, name: str) -> tuple[bytes, str]:
        prerequisites_dir = Path(__file__).with_name('prerequisites')
        script_name = shlex.quote(name) + '.sh'
        script_path = prerequisites_dir / self._model / self._arch / self._os / script_name
        script_body = script_path.read_bytes()
        sha_hash = hashlib.sha1()
        sha_hash.update(script_name.encode())
        sha_hash.update(script_path.read_bytes())
        return script_body, sha_hash.hexdigest()


class _GenericMachine(_ScriptDescribedMachine):

    def make_request(self, *disk_stems: str) -> Mapping[str, Any]:
        return {
            'model': self._model,
            'arch': self._arch,
            'os': self._os,
            'disk_stems': disk_stems,
            }

    def __repr__(self):
        return f'<{self.__class__.__name__}: [{self._model}|{self._arch}|{self._os}]>'


class _NamedMachine(_ScriptDescribedMachine):

    def __init__(self, model: str, arch: str, os: str, name: str):
        super().__init__(model, arch, os)
        self._name = name

    def make_request(self, *disk_stems: str) -> Mapping[str, Any]:
        return {
            'model': self._model,
            'arch': self._arch,
            'os': self._os,
            'name': self._name,
            'disk_stems': disk_stems,
            }

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._name} [{self._model}|{self._arch}|{self._os}]>'
