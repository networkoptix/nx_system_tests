# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from mediaserver_api import AuditTrail
from real_camera_tests.checks import Failure
from real_camera_tests.checks import Skipped
from real_camera_tests.checks import Success
from real_camera_tests.server_stage import Run

_logger = logging.getLogger(__name__)


def _check_metrics(run: Run, offline_statuses_limit: int, transactions_limit: int):
    metrics = run.server.api.http_get('api/metrics?brief')
    errors = []

    def check(path, limit):
        actual = metrics
        for k in path:
            actual = actual[k]
        if actual > limit:
            errors.append(f"{'/'.join(path)}: {actual} > {limit}")

    check(['offlineStatus'], offline_statuses_limit)
    check(['transactions', 'errors'], 0)
    check(['transactions', 'local'], 10)
    check(['transactions', 'success'], transactions_limit)
    if errors:
        return Failure(errors)
    return Success(metrics)


def metrics_before(run: Run):
    return _check_metrics(
        run,
        run.expected_cameras.server_config.offline_statuses_limit_before,
        run.expected_cameras.server_config.transactions_limit_before)


def metrics_after(run: Run):
    # TODO: Why does manual discovery lead to camera offline statues?
    return _check_metrics(
        run,
        run.expected_cameras.server_config.offline_statuses_limit_after,
        run.expected_cameras.server_config.transactions_limit_after)


def auto_discovery_in_audit_trail(run: Run):
    audit_trail = AuditTrail(run.server.api, skip_initial_records=False)
    events = audit_trail.wait_for_sequence()
    for event in events:
        if event.type == run.server.api.audit_trail_events.CAMERA_INSERT:
            return Failure("CameraInsert event is in audit trail for auto discovered camera.")
    return Success(info='No CameraInsert events for auto discovered cameras in audit trail.')


def _check_unexpected_cameras(actual_cameras, expected_camera_ids):
    unexpected_cameras = []

    for camera in actual_cameras:
        _logger.debug(camera)
        if camera.physical_id not in expected_camera_ids:
            unexpected_cameras.append(camera)

    if unexpected_cameras:
        return Failure(f"{len(unexpected_cameras)} unexpected cameras found: {unexpected_cameras}")

    return Success()


def unexpected_cameras_after_autodiscovery(run: Run):
    expected_camera_ids = run.expected_cameras.physical_ids_auto
    actual_cameras = run.server.api.list_cameras()
    return _check_unexpected_cameras(actual_cameras, expected_camera_ids)


def cancel_auto_discovery(run: Run):
    # Need to disable auto discovery before removing the cameras
    run.server.api.set_system_settings({'autoDiscoveryEnabled': 'false'})
    _logger.info("Wait after disabling auto discovery for running searchers to stop")
    time.sleep(40)
    for uuid in [item['id'].strip('{}') for item in run.server.api.http_get('ec2/getCameras')]:
        run.server.api.remove_resource(uuid)
    started_at = time.monotonic()
    while True:
        cameras_list = run.server.api.http_get('ec2/getCameras')
        if not cameras_list:
            return Success(info="All previously discovered cameras were removed successfully")
        if time.monotonic() - started_at > 10:
            return Failure({'cameras_that_still_present': cameras_list})
        time.sleep(1)


def camera_count_metrics(run: Run):
    system_info_cameras = run.server.api.get_metrics('system_info', 'cameras')
    server_id = run.server.api.get_server_id()
    server_cameras = run.server.api.get_metrics('servers', server_id, 'cameras')
    metrics = [('system_info', system_info_cameras), ('servers', server_cameras)]
    failure_message = ""
    for metric, camera_count in metrics:
        if run.expected_cameras.camera_count_metric != camera_count:
            failure_message += f"{metric} camera count: {camera_count}; "
    if failure_message:
        actual_cameras = [
            dict(name=camera.name, url=camera.url)
            for camera in run.server.api.list_cameras()]
        failure_message += f"expected camera count: {run.expected_cameras.camera_count_metric}; "
        failure_message += f"actual cameras: {actual_cameras}"
        return Failure(failure_message)

    return Success()


def unexpected_cameras_after_manual_discovery(run: Run):
    expected_camera_ids = run.expected_cameras.physical_ids_manual
    actual_cameras = run.server.api.list_cameras()
    return _check_unexpected_cameras(actual_cameras, expected_camera_ids)


# https://networkoptix.testrail.net/index.php?/cases/view/46917
def change_nvr_names(run: Run, is_after_auto=True):
    started_at = time.monotonic()
    group_ids = set()
    if is_after_auto:
        nvr_ids = [nvr_id.auto for nvr_id in run.expected_cameras.nvr_physical_ids]
    else:
        nvr_ids = [nvr_id.manual for nvr_id in run.expected_cameras.nvr_physical_ids]
    _logger.info("Searching for NVRs with the following IDs: %s", nvr_ids)
    for nvr_id in nvr_ids:
        nvr = run.server.api.get_camera(camera_id=nvr_id, is_uuid=False)
        if nvr is None:
            _logger.warning("Cannot discover NVR: %s", nvr_id)
            continue
        group_ids.add(nvr_id)  # For child cameras of the NVR node group ID is NVR's physical ID
    if not group_ids:
        return Skipped("No NVRs from filtered config in the mediaserver DB")
    group_id_to_camera_ids = {}
    while True:
        for camera in run.server.api.list_cameras():
            if camera.group_id not in group_ids:
                continue
            group = group_id_to_camera_ids.setdefault(camera.group_id, [])
            group.append(camera.id)
        if len(group_id_to_camera_ids) == len(group_ids):
            break
        if time.monotonic() - started_at > 30:
            return Failure("Some NVR group IDs do not belong to any cameras")
        time.sleep(1)
    for group_id, camera_ids in group_id_to_camera_ids.items():
        _logger.info("%d cameras have group ID %s", len(camera_ids), group_id)
        old_name = run.server.api.get_camera(camera_ids[-1]).group_name
        new_name = f"{old_name}_NewNvrNameForRct"
        _logger.info("Rename group %s, old name: %s, new name: %s", group_id, old_name, new_name)
        run.server.api.change_cameras_group_name(camera_ids, new_name)
        while True:
            current_group_names = set()
            for camera_id in camera_ids:
                current_group_names.add(run.server.api.get_camera(camera_id).group_name)
            if all([new_name == current_name for current_name in current_group_names]):
                break
            if time.monotonic() - started_at > 60:
                return Failure(f"Timed out: group name not set for cameras from group {group_id}")
            time.sleep(1)
    return Success()
