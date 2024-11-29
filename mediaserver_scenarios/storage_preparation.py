# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from collections import namedtuple

from mediaserver_api import WrongPathError


def create_smb_share(smb_os_access, user, password, size, letter, quota=None):
    name = f'{letter}_{user}_{password}'
    mount_point = smb_os_access.mount_fake_disk(letter, size)
    if quota is not None:
        smb_os_access.set_disk_quota(letter, quota)
    path = mount_point / 'Share'
    path.rmtree(ignore_errors=True)
    path.mkdir()
    if user:
        smb_os_access.create_user(user, password, exist_ok=True)
        smb_os_access.allow_access(path, user)
    else:
        smb_os_access.allow_access_for_everyone(path)
    smb_os_access.create_smb_share(name, path, user)
    return name, path


def _choose_disk_to_mount(os_access):
    letters = ['S', 'M', 'L', 'N', 'K']
    for attempted_letter in letters:
        if not os_access.is_fake_disk_mounted(attempted_letter):
            return attempted_letter
    raise RuntimeError(f"All disks {letters} are already mounted")


def add_local_storage(mediaserver, storage_size_bytes=300 * 1024**3):
    letter = _choose_disk_to_mount(mediaserver.os_access)
    mediaserver.stop()
    path = mediaserver.os_access.mount_fake_disk(letter, storage_size_bytes)
    mediaserver.start()
    mediaserver.api.list_storages()
    return path


_SmbShare = namedtuple('SmbShare', 'url local_path id')


def _prepare_smb_storage(
        smb_server_os_access,
        user,
        password,
        storage_size_bytes=300 * 1024**3,
        quota=None,
        ):
    # Password longer 14 characters triggers interactive message:
    # "The password entered is longer than 14 characters. Computers with windows prior
    # windows 2000 will not be able to use this account. Continue? (Y/N) [Y]:"
    # Interactive mode leads to create_user failure.
    letter = _choose_disk_to_mount(smb_server_os_access)
    share_name, share_path = create_smb_share(
        smb_server_os_access, user, password, storage_size_bytes, letter, quota=quota)
    return share_name, share_path


def add_smb_storage(
        mediaserver_api,
        smb_server_os_access,
        smb_server_host: str,
        storage_size_bytes=300 * 1024**3,
        quota=None,
        user='OnlineUser',
        password='OnlinePass',
        ):
    [share_name, share_path] = _prepare_smb_storage(
        smb_server_os_access,
        user,
        password,
        storage_size_bytes=storage_size_bytes,
        quota=quota)
    # The SMB storage may be inaccessible immediately after creation. Give it another attempt.
    attempt = 0
    while True:
        attempt += 1
        try:
            # Workaround for VMS-16364: first 'list_storages' request after adding inaccessible SMB
            # storage to mediaserver will hang. Make it with longer timeout.
            storage_id = mediaserver_api.add_smb_storage(
                smb_server_host, share_name, user, password, init_timeout=120)
        except WrongPathError:
            if attempt >= 2:
                raise
            time.sleep(1)
        else:
            break
    return _SmbShare(f'smb://{smb_server_host}/{share_name}', share_path, storage_id)


def add_offline_smb_storage(mediaserver_api, smb_server_os_access, smb_server_host: str):
    smb_share = add_smb_storage(
        mediaserver_api,
        smb_server_os_access,
        smb_server_host,
        user='OfflineUser',
        password='OfflinePass')
    smb_server_os_access.deny_access(smb_share.local_path, 'OfflineUser')
    started = time.monotonic()
    timeout_sec = 60
    while time.monotonic() - started < timeout_sec:
        [smb_storage] = mediaserver_api.list_storages(
            within_path=smb_share.url, ignore_offline=True)
        smb_storage_metric = mediaserver_api.get_metrics('storages', smb_storage.id)
        if not smb_storage.is_writable and smb_storage_metric['status'] == 'Inaccessible':
            return smb_share
    raise RuntimeError(f"SMB share {smb_share} is still online after {timeout_sec} seconds.")


def add_network_storage(
        mediaserver_api,
        mediaserver_os_access,
        smb_server_os_access,
        smb_server_host: str,
        storage_size_bytes=300 * 1024**3,
        quota=None,
        user='NetworkStorageUser',
        password='StoragePass',
        ):
    # SMB share mounted via OS will have type "network" in mediaserver.
    [share_name, _] = _prepare_smb_storage(
        smb_server_os_access,
        user,
        password,
        storage_size_bytes=storage_size_bytes,
        quota=quota)
    mount_point = '/mnt/networkStorage'
    mediaserver_os_access.mount_smb_share(
        mount_point=mount_point,
        path=f'//{smb_server_host}/{share_name}',
        username=user,
        password=password,
        )
    mediaserver_api.set_up_new_storage(mount_point)
    return mount_point
