# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import recording_camera


# Numbers are chosen not to be whole seconds.
def _test_long_event(distrib_url, one_vm_type, api_version, duration_ms, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    camera_id = exit_stack.enter_context(recording_camera(mediaserver, sample_media_file)).id
    mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.bookmark(None, [str(camera_id)]),
        )
    mediaserver.api.create_event(
        source="Any source",
        caption="Caption that won't appear in the bookmark",
        description="Description that won't appear in the bookmark",
        state=EventState.ACTIVE,
        )
    assert not mediaserver.api.list_bookmarks(camera_id)
    time.sleep(duration_ms / 1000)
    assert not mediaserver.api.list_bookmarks(camera_id)
    caption = "Name for bookmark"
    description = "Description for bookmark"
    mediaserver.api.create_event(
        source="Another any source",
        caption=caption,
        description=description,
        state=EventState.INACTIVE,
        )
    bookmark, = mediaserver.api.list_bookmarks(camera_id)
    assert bookmark.camera_id == camera_id
    assert bookmark.description == description

    # There's network delays between autotest and mediaserver remote (for instance, ARM device)
    # hosts, 150 ms as an approximation value should be enough in this case.
    assert math.isclose(bookmark.duration_ms, duration_ms, abs_tol=150)
    assert bookmark.name == caption
