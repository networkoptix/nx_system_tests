# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import recording_camera


def _test_event_stop(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    camera_id = exit_stack.enter_context(recording_camera(mediaserver, sample_media_file)).id
    action = RuleAction.bookmark(10000, [str(camera_id)])
    mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.INACTIVE,
        action=action,
        )
    # For prolonged events, the initial "Inactive" state is ignored
    # if there was no "Active" state before it (VMS-23318)
    mediaserver.api.create_event(
        source="Any source",
        caption="Generic start (activation) event",
        description="Description for bookmark (activation)",
        state=EventState.ACTIVE,
        )
    assert not mediaserver.api.list_bookmarks(camera_id)
    caption = "Generic stop (inactivation) event"
    description = "Description for bookmark"
    mediaserver.api.create_event(
        source="Any source",
        caption=caption,
        description=description,
        state=EventState.INACTIVE,
        )
    bookmark, = mediaserver.api.list_bookmarks(camera_id)
    assert bookmark.camera_id == camera_id
    assert bookmark.description == description
    assert bookmark.duration_ms == action.params['durationMs']
    assert bookmark.name == caption
