# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import json
import logging

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from distrib import Distrib
from installation import ClassicInstallerSupplier
from mediaserver_api import DEFAULT_FULL_INFO_DIFF_WHITE_LIST
from mediaserver_api import Diff
from mediaserver_api import MotionType
from mediaserver_api import PathPattern
from mediaserver_api import Permissions
from mediaserver_api import full_info_differ
from mediaserver_api import log_diff_list
from mediaserver_api import whitelist_diffs
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from os_access import copy_file

_logger = logging.getLogger(__name__)


def _configure_mediaserver_with_restored_backup(one_mediaserver: OneMediaserverStand, restore_mode, backup_path, metadata):
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({
        'guidIsHWID': 'false',
        'serverGuid': metadata['server_guid'],
        })

    if restore_mode == 'db':
        copy_file(backup_path, mediaserver.ecs_db)

    mediaserver.start()

    setup_wizard_is_expected = metadata['setup_wizard_is_expected'].lower() == 'true'
    admin_password_in_backup = 'WellKnownPassword2'

    if restore_mode == 'db':
        system_is_set_up = mediaserver.api.system_is_set_up()
        assert system_is_set_up == (not setup_wizard_is_expected), (
            "Mediaserver setup wizard is %s, but %s" % (
                "not presented" if system_is_set_up else "presented",
                "expected" if setup_wizard_is_expected else "not expected"))

    if restore_mode == 'backup' or setup_wizard_is_expected:
        mediaserver.api.setup_local_system({'autoDiscoveryEnabled': 'false'})
    else:
        mediaserver.api.set_password(admin_password_in_backup)

    if restore_mode == 'backup':
        base64_backup_data = base64.b64encode(backup_path.read_bytes())
        with mediaserver.api.waiting_for_restart(120):
            mediaserver.api.restore_database(base64_backup_data)

    return mediaserver


def _expected_diffs(backup_ver, distrib: Distrib, server):
    black_list = [
        # These properties are independent of the mediaserver version,
        # but depend on the machine and OS the server is running on
        'servers/*/flags',
        'servers/*/networkAddresses',
        'servers/*/osInfo/**',
        'servers/*/url',
        'servers/*/version',
        # Admin user is changed after restore
        'users/admin/cryptSha512Hash',
        'users/admin/digest',
        'users/admin/hash',
        # FT-1135: According to server team lead, this option exists only for compatibility purposes
        'cameraUserAttributesList/*/licenseUsed',
        # Blacklisted since 5.0.
        'cameras/*/url',
        'cameraUserAttributesList/*/backupContentType',
        'cameraUserAttributesList/*/backupPolicy',
        'cameraUserAttributesList/*/backupQuality',
        'cameraUserAttributesList/*/backupType',
        'cameraUserAttributesList/*/dataAccessId',
        'cameraUserAttributesList/*/replaceWithId',  # New name of dataAccessId field
        'cameraUserAttributesList/*/scheduleTasks/*/metadataTypes',
        'serversUserAttributesList/*/backupBitrateBytesPerSecond',
        'serversUserAttributesList/*/backupBitrate',
        'serversUserAttributesList/*/backupDaysOfTheWeek',
        'serversUserAttributesList/*/backupDuration',
        'serversUserAttributesList/*/backupStart',
        'serversUserAttributesList/*/backupType',
        # This feature was added since 5.0.
        'cameraUserAttributesList/*/maxArchivePeriodS',
        'cameraUserAttributesList/*/minArchivePeriodS',
        ]
    if server.api.specific_features().get('user_role_id_list_support'):
        black_list = [
            *black_list,
            'users/*/userRoleId',
            ]
    if server.api.specific_features().get('user_attributes'):
        black_list = [
            *black_list,
            'users/*/attributes',
            ]
    if server.api.specific_features().get('minimal_internal_api', 2):
        black_list = [
            *black_list,
            'users/*/isAdmin',
            'users/*/realm',
            'users/*/type',
            'users/*/isCloud',
            'users/*/isLdap',
            'users/*/groupIds',
            ]
    if server.api.specific_features().get('ldap_support'):
        black_list = [
            *black_list,
            'users/*/externalId',
            ]
    if distrib.newer_than('vms_5.1'):
        black_list.extend([
            'users/*/integrationRequestData',
            ])
    if distrib.newer_than('vms_5.0'):
        black_list = [
            *black_list,
            'serversUserAttributesList/*/metadataStorageId',
            ]
    if distrib.newer_than('vms_6.0'):
        black_list.extend([
            'users/*/locale',
            ])
    version_as_tuple = tuple(map(int, backup_ver.split('.')))
    if version_as_tuple <= (5, 0):
        black_list = [
            *black_list,
            'serversUserAttributesList/*/locationId',
            'users/*/userRoleIds',
            ]
    if version_as_tuple <= (4, 0):
        black_list = [
            *black_list,
            'servers/*/systemInfo',
            'serversUserAttributesList/*/metadataStorageId',
            'videowalls/*/timeline',
            ]
    if version_as_tuple <= (2, 6):
        black_list = [
            *black_list,
            'cameraUserAttributesList/*/cameraID',
            'cameraUserAttributesList/*/preferedServerId',  # noqa SpellCheckingInspection
            'cameraUserAttributesList/*/secondaryStreamQuality',
            'cameraUserAttributesList/*/scheduleTasks/*/afterThreshold',
            'cameraUserAttributesList/*/scheduleTasks/*/beforeThreshold',
            'cameraUserAttributesList/*/scheduleTasks/*/recordAudio',
            'servers/*/apiUrl',
            'servers/*/not_used',
            'servers/*/systemName',
            'serversUserAttributesList/*/serverID',
            'cameraUserAttributesList/*/cameraId',
            'cameraUserAttributesList/*/disableDualStreaming',
            'cameraUserAttributesList/*/logicalId',
            'cameraUserAttributesList/*/preferredServerId',
            'cameraUserAttributesList/*/recordAfterMotionSec',
            'cameraUserAttributesList/*/recordBeforeMotionSec',
            'cameraUserAttributesList/*/scheduleTasks/*/bitrateKbps',
            'serversUserAttributesList/*/serverId',
            'users/*/fullName',
            'users/*/isCloud',
            'users/*/userRoleId',
            'servers/*/authKey',
            ]
    if version_as_tuple <= (2, 4, 1):
        black_list = [
            *black_list,
            'cameraUserAttributesList/*/backupType',
            'serversUserAttributesList/*/backupBitrate',
            'serversUserAttributesList/*/backupDaysOfTheWeek',
            'serversUserAttributesList/*/backupDuration',
            'serversUserAttributesList/*/backupStart',
            'serversUserAttributesList/*/backupType',
            ]
    if distrib.specific_features().get('multiple_user_roles') == 2:
        black_list.extend([
            'users/USER/permissions',
            'users/admin/permissions',
            ])
    if distrib.specific_features().get('users_and_groups'):
        black_list.extend([
            'users/USER/resourceAccessRights',
            'users/admin/resourceAccessRights',
            ])
    return black_list


def _expected_renames(backup_ver):
    expected_renames = {}
    version_as_tuple = tuple(map(int, backup_ver.split('.')))
    if version_as_tuple <= (2, 6):
        expected_renames = {
            'users/*/permissions': {
                '255': Permissions.ADMIN,
                '128': Permissions.CUSTOM_USER,
                },
            'users/admin/realm': {
                'networkoptix': 'VMS',
                },
            }
    # Note about cameraUserAttributesList/*/motionType:
    # In 2.4.1 and 2.6 it was a value like MT_SoftwareGrid or MT_Default;
    # from 3.1 to 4.2, these were integers like 2 or 0;
    # from 5.0 onwards these are values such as software or default
    if version_as_tuple <= (2, 6):
        expected_renames = {
            **expected_renames,
            'cameraUserAttributesList/*/motionType': {
                'MT_SoftwareGrid': 'software',
                'MT_Default': 'default',
                },
            }
    if (3, 1) <= version_as_tuple <= (4, 2):
        expected_renames = {
            **expected_renames,
            'cameraUserAttributesList/*/motionType': {
                str(MotionType.NONE.value): 'none',
                },
            }
    return expected_renames


def _is_in_expected_diffs(diff, expected_diffs):
    for pattern_str in expected_diffs:
        pattern = PathPattern(pattern_str)
        if pattern.match(diff.path):
            return True
        if pattern.match(diff.path + [diff.x]):
            return True
        if pattern.match(diff.path + [diff.y]):
            return True
    return False


def _is_expected_changes(diff, expected_renames):
    if diff.action != 'changed':
        return False
    for key in expected_renames:
        if PathPattern(key).match(diff.path):
            break
    else:
        return False
    if diff.x not in expected_renames[key]:
        return False
    return expected_renames[key][diff.x] == diff.y


def _remove_expected_diffs(diff_list, expected_diffs, expected_renames):
    result_diff = []
    for item in diff_list:
        if _is_in_expected_diffs(item, expected_diffs):
            continue
        if _is_expected_changes(item, expected_renames):
            continue
        result_diff.append(item)
    return result_diff


# Implements FT-223
def _test_restore_from_old_version(distrib_url, one_vm_type, restore_mode, backup_ver, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    metadata = default_prerequisite_store.fetch(f'restore-old-backup-test/{backup_ver}-metadata.yaml').read_text()
    metadata = dict(line.split(': ', 1) for line in metadata.splitlines())
    backup_path = default_prerequisite_store.fetch(f'restore-old-backup-test/{backup_ver}-backup.db')
    expected_full_info = json.loads(
        default_prerequisite_store.fetch(f'restore-old-backup-test/{backup_ver}-full-info.json').read_text())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    server = _configure_mediaserver_with_restored_backup(one_mediaserver, restore_mode, backup_path, metadata)
    expected_diffs = _expected_diffs(backup_ver, distrib, server)
    expected_renames = _expected_renames(backup_ver)
    artifacts_dir = get_run_dir()
    server.api.enable_basic_and_digest_auth_for_admin()
    # The full info in the backups was prepared using the ec2/getFullInfo endpoint.
    # Thus, the test must use the same endpoint.
    full_info = server.api.http_get('ec2/getFullInfo', timeout=240)
    full_info_path = artifacts_dir.joinpath('full_info.json')
    full_info_path.write_text(json.dumps(full_info, indent=4))

    diff_list = full_info_differ.diff(expected_full_info, full_info)
    artifacts_dir.joinpath('full-info-diff.txt').write_text(Diff.list_to_str(diff_list))
    _logger.info('Full diffs:')
    log_diff_list(_logger.info, diff_list)

    whitelisted_diff_list = whitelist_diffs(
        diff_list, DEFAULT_FULL_INFO_DIFF_WHITE_LIST)
    cleared_diff = _remove_expected_diffs(
        whitelisted_diff_list, expected_diffs, expected_renames)
    # After VMS-13974 the virtual desktop cameras are omitted in API responses
    # due to security reasons. Currently, expected_diffs doesn't support adding
    # items by action and message. Changing the expected_diffs format seems too
    # heavy, so diff is modified right here for this case.
    cleared_diff = [diff for diff in cleared_diff if not _diff_is_for_removed_virtual_camera(diff)]

    artifacts_dir.joinpath('full-info-diff-cleared.txt').write_text(Diff.list_to_str(cleared_diff))
    _logger.info('Whitelisted diffs:')
    log_diff_list(_logger.info, cleared_diff)

    assert not cleared_diff, 'Got unexpected diff after restoring from previous version backup'


def _diff_is_for_removed_virtual_camera(diff):
    if diff.path[0] != 'cameras':
        return False
    if diff.action != 'removed':
        return False
    if diff.message['model'] != 'virtual desktop camera':
        return False
    return True
