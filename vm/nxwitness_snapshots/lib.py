# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import logging
import os
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from _internal.service_registry import vms_build_registry
from vm.hypervisor import Hypervisor
from vm.nxwitness_snapshots._plugin_interface import SnapshotPlugin
from vm.vm import VM
from vm.vm_type import VMSnapshotTemplate


class PrebuiltSnapshotStrategy:
    """Use pre-built snapshots with an installed product to create VMs."""

    def __init__(
            self,
            hypervisor: Hypervisor,
            artifact_dir: Path):
        self._hypervisor = hypervisor
        self._artifact_dir = artifact_dir

    @contextmanager
    def clean_vm(self, vm_type: VMSnapshotTemplate) -> AbstractContextManager[VM]:
        snapshot_uri = self._hypervisor.get_base_snapshot_uri(vm_type.name())
        with vm_type.vm_locked(snapshot_uri) as vm:
            yield vm

    def create_snapshot(self, plugin: SnapshotPlugin, vm_type: VMSnapshotTemplate) -> str:
        root_disk_url = self._hypervisor.get_base_snapshot_uri(vm_type.name())
        name = vm_type.name()
        prefix = plugin.name_prefix(name)
        with vm_type.vm_locked(root_disk_url) as vm:
            vm.ensure_started(self._artifact_dir)
            try:
                plugin.prepare(vm.os_access, self._artifact_dir)
            finally:
                vm.os_access.download_system_logs(self._artifact_dir)
            vm.os_access.compact()
            vm.vm_control.shutdown(timeout_sec=60)
            snapshot_uri = vm.vm_control.save_as_plugin_snapshot(root_disk_url, prefix)
        _publish_snapshot(vm_type.name(), root_disk_url, snapshot_uri, plugin)
        return snapshot_uri

    @contextmanager
    def vm_created(self, plugin, vm_type: VMSnapshotTemplate):
        latest_record = _get_latest_snapshot_record(plugin, vm_type.name())
        root_disk_url, mediaserver_disk_url = latest_record.disks_urls()
        with vm_type.vm_locked(mediaserver_disk_url, parent_uri=root_disk_url) as vm:
            yield vm


def _get_latest_snapshot_record(plugin, os_name):
    snapshot_creator = os.getenv('SNAPSHOT_CREATOR_NAME') or getpass.getuser()
    builds_with_snapshots = vms_build_registry.list_builds_with_snapshot(
        plugin.name_prefix(os_name),
        os_name,
        snapshot_creator,
        )
    try:
        [latest_record, *_] = builds_with_snapshots
    except ValueError:
        raise RuntimeError(
            f"No snapshots for OS {os_name!r} with plugin {plugin!r} from creator "
            f"{snapshot_creator!r} are found. "
            f"To create a new local snapshot, run command "
            f"'python3 -m make_venv -m {plugin.__class__.__module__}' with necessary arguments. "
            f"To download GitLab pipeline snapshots, run original script with environment "
            "variable SNAPSHOT_CREATOR_NAME=ft")
    return latest_record


def _publish_snapshot(
        os_name: str,
        root_disk_url: str,
        mediaserver_url: str,
        plugin: SnapshotPlugin,
        ):
    for url in (mediaserver_url, root_disk_url):
        parsed = urlparse(url)
        # For locally built snapshots, the URL is created with the 'file' scheme.
        if parsed.scheme not in ('http', 'https', 'file'):
            raise SnapshotPublishError(
                f"The publishing URL scheme must be http, https of file, got ({url!r})")
    build_record = plugin.build_record().with_snapshot(
        plugin.name_prefix(os_name),
        os_name,
        root_disk_url,
        mediaserver_url,
        )
    vms_build_registry.add_record(build_record.raw())


class SnapshotPublishError(RuntimeError):
    pass


_logger = logging.getLogger(__name__)
