# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import datetime
from datetime import timezone

from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import TwoMediaserverStand
from tests.waiting import wait_for_equal


def configure_two_mediaservers_stand(two_mediaservers: TwoMediaserverStand):
    """Make sure mediaservers are installed, stopped and internet is disabled."""
    primary = two_mediaservers.first.installation()
    secondary = two_mediaservers.second.installation()
    primary.os_access.set_datetime(datetime.now(timezone.utc))
    secondary.os_access.set_datetime(datetime.now(timezone.utc))
    primary.start()
    primary.api.setup_local_system()
    secondary.start()
    secondary.api.setup_local_system()
    merge_systems(primary, secondary, take_remote_settings=False)
    primary_guid = primary.api.get_server_id()
    primary.api.become_primary_time_server()
    # The following may follow the intent of C1598.
    wait_for_equal(primary.api.get_primary_time_server_id, primary_guid)
    wait_for_equal(secondary.api.get_primary_time_server_id, primary_guid)
    primary.api.wait_for_time_synced()


_logger = logging.getLogger(__name__)
