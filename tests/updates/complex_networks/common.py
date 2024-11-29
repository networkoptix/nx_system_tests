# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from installation import UpdateServer


def perform_system_update(updates_supplier, mediaservers, platforms):
    for server in mediaservers:
        server.stop()
        server.disable_update_files_verification()
        server.start()
    for server in mediaservers:
        server.api.wait_for_neighbors_status('Online', timeout_sec=30)
    [mediaserver, *_] = mediaservers
    update_archive = updates_supplier.fetch_server_updates(platforms)
    update_server = UpdateServer(update_archive, mediaserver.os_access.source_address())
    with update_server.serving():
        mediaserver.api.start_update(update_server.update_info())
        # FT-2123: Log system servers to check merge status.
        try:
            mediaserver.api.wait_until_update_ready_to_install(timeout_sec=600)
        except RuntimeError as e:
            if "Unexpected update code: offline" in str(e):
                mediaserver.api.list_servers()
            raise
        with mediaserver.api.waiting_for_restart(timeout_sec=300):
            mediaserver.api.install_update()
        if mediaserver.api.get_version() != updates_supplier.distrib().version():
            raise RuntimeError("Version of updated system does not match")
