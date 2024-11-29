# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod

from _internal.service_registry import gui_prerequisite_store
from directories.prerequisites import PrerequisiteStore
from os_access import OsAccess
from os_access import RemotePath
from os_access import copy_file

_logger = logging.getLogger(__name__)


class Supplier(metaclass=ABCMeta):
    """Deliver a file to a remote machine.

    There are multiple options in theory:
    - upload from the host where this code runs,
    - download directly via HTTP using a guest OS utility,
    - on a VM, use a shared folder,
    - on AWS, use S3 bucket and the aws utility.
    """

    @abstractmethod
    def upload_to_remote(self, relative_path, remote_os_access):
        pass


class DirectUploadSupplier(Supplier):

    def __init__(self, warehouse: PrerequisiteStore):
        self._warehouse: PrerequisiteStore = warehouse

    def upload_to_remote(self, relative_path: str, remote_os_access: OsAccess) -> RemotePath:
        # Files in tmp() folder on Linux do not survive system restart.
        remote_path = remote_os_access.home() / relative_path
        if not remote_path.exists():
            remote_path.parent.mkdir(parents=True, exist_ok=True)
            local_path = self._warehouse.fetch(relative_path)
            copy_file(local_path, remote_path)
        return remote_path


gui_prerequisite_supplier: Supplier = DirectUploadSupplier(gui_prerequisite_store)
