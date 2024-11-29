# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from vm.hypervisor import DiskInUse
from vm.virtual_box._disk_exceptions import DiskExists
from vm.virtual_box._disk_exceptions import DiskNotFound
from vm.virtual_box._disk_exceptions import ParentDiskNotFound
from vm.virtual_box._hypervisor_exceptions import VirtualBoxError
from vm.virtual_box._hypervisor_exceptions import virtual_box_error_cls
from vm.virtual_box._vboxmanage import get_virtual_box
from vm.virtual_box._vboxmanage import vboxmanage


def vbox_manage_create_medium(path: str, size_mb: int):
    command = [
        'createmedium',
        '--filename', path,
        '--format', 'VDI',
        '--size', str(size_mb)]
    vboxmanage(command)
    get_virtual_box().fix_permissions(Path(path))  # To read and write metadata


def vbox_manage_close_medium(path: Path):
    # In rare cases VirtualBox can fail to remove media while returning 0:
    # > $ VBoxManage closemedium disk ft0-xenial-01.vdi --delete; echo $?
    # > VBoxManage: error: Could not open the medium '/home/user/.cache/nx-func-tests/linked-templates/ubuntu16_msver_5.0.0.1474.vdi'.
    # > VBoxManage: error: VD: error VERR_FILE_NOT_FOUND opening image file '/home/user/.cache/nx-func-tests/linked-templates/ubuntu16_msver_5.0.0.1474.vdi'
    # > VBoxManage: error: Details: code NS_ERROR_FAILURE (0x80004005), component MediumWrap, interface IMedium, callee nsISupports
    # > VBoxManage: error: Context: "DeleteStorage(pProgress.asOutParam())" at line 1727 of file VBoxManageDisk.cpp
    # > VBoxManage: error: Failed to delete medium. Error code Unknown Status -2147467259 (0x80004005)
    # > 0
    # Manual disk file removal is necessary if no exception raised.
    try:
        vboxmanage(['closemedium', 'disk', str(path), '--delete'])
    except virtual_box_error_cls('VBOX_E_FILE_ERROR'):
        _logger.debug("Disk image %s: Not registered", path)
    except virtual_box_error_cls('VBOX_E_INVALID_OBJECT_STATE') as e:
        if 'is locked for reading by another task' in e.error_text:
            raise DiskInUse(f"Disk {path} is in use")
        raise
    except virtual_box_error_cls('VBOX_E_OBJECT_IN_USE') as e:
        if 'because it has' in e.error_text and 'child media' in e.error_text:
            raise DiskInUse(f"Disk {path} is in use")
        raise
    except virtual_box_error_cls('NS_ERROR_FAILURE') as e:
        if 'is not found in the media registry' not in e.error_text:
            raise
    except virtual_box_error_cls('VBOX_E_IPRT_ERROR') as e:
        if 'Could not get the storage format' not in e.error_text:
            raise
    else:
        _logger.debug("Disk image %s: Unregistered", path)
    path.unlink(missing_ok=True)


def vbox_manage_register_medium(location: Path):
    """Add disk to VirtualBox.xml.

    To perform an action on a differencing disk its parent must be specified in
    the MediaRegistry section in the VirtualBox.xml.
    There is no direct VBoxManage command to add a disk to the VirtualBox.xml.
    Read-only operations on a disk (such as 'showmediuminfo') do not add disk
    to the VirtualBox.xml.
    The reason 'showmediuminfo' worked is anchor disk creation right after show
    command, which results in a record in the VirtualBox.xml.
    As a workaround 'mediumproperty get' and 'mediumproperty set' are used
    to add a disk to the VirtualBox.xml.
    The only property available is AllocationBlockSize.
    'mediumproperty set' does not require write permissions on a disk file.
    """
    try:
        result = vboxmanage(['mediumproperty', 'get', str(location), 'AllocationBlockSize'])
    except virtual_box_error_cls("VBOX_E_FILE_ERROR") as err:
        if 'Could not find file for the medium' in err.error_text:
            raise DiskNotFound(f"Can't find disk identified by {location}")
        raise
    except virtual_box_error_cls("NS_ERROR_FAILURE") as err:
        if 'is not found in the media registry' in err.error_text:
            raise ParentDiskNotFound(f"Can't find parent for disk identified by {location}")
        raise
    [_, _, block_size] = result.partition('=')
    if not block_size:
        raise RuntimeError(f"Failed to get AllocationBlockSize for {location}")
    try:
        vboxmanage(['mediumproperty', 'set', str(location), 'AllocationBlockSize', block_size])
    except virtual_box_error_cls('VBOX_E_INVALID_OBJECT_STATE') as err:
        if 'is locked for reading by another task' not in err.error_text:
            raise
        _logger.debug("%s is already registered", location)


def vbox_manage_create_child_medium(parent: Path, child: Path):
    try:
        command = [
            'createmedium',
            '--filename',
            str(child),
            '--diffparent',
            str(parent)]
        vboxmanage(command)
    except virtual_box_error_cls('VBOX_E_FILE_ERROR') as err:
        if 'Could not find file for the medium' in err.error_text:
            raise ParentDiskNotFound(
                f"Can't find parent disk {parent.absolute()} for disk"
                f"identified by {child.absolute()}")
        if 'VERR_ALREADY_EXISTS' not in err.error_text:
            raise
        raise DiskExists(f"Child disk {child.absolute()} already exists")
    except VirtualBoxError as e:
        if child.exists() and 'Failed to create medium' in str(e):
            raise DiskExists(f"Child disk {child.absolute()} already exists")
        raise
    get_virtual_box().fix_permissions(child)  # To read and write metadata
    description = _vbox_get_medium_description(parent)
    _vbox_set_medium_description(child, description)


def _vbox_set_medium_description(path: Path, description: str) -> None:
    data = description.encode() + b'\0'
    if len(data) > 256:
        raise ValueError("Description is too long")
    with open(path, 'rb+') as fd:
        fd.seek(76 + 8)
        fd.write(data + b'\0')


def _vbox_get_medium_description(path: Path) -> str:
    with open(path, 'rb') as fd:
        fd.seek(76 + 8)
        data = fd.read(256)
    data, _, _ = data.partition(b'\0')
    return data.decode()


_logger = logging.getLogger(__name__)
