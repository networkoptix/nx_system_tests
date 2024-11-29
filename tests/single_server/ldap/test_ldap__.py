# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.software_cameras import data_is_jpeg_image
from doubles.video.ffprobe import wait_for_stream
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_ldap(distrib_url, one_vm_type, ldap_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    openldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    [ldap_server_unit, mediaserver_unit] = openldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    api.setup_local_system()

    camera_server = MultiPartJpegCameraServer()
    cameras_count = 5
    cameras = add_cameras(mediaserver, camera_server, indices=range(cameras_count))
    layout_id = api.add_layout('test_layout')

    generated_ldap_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_ldap_user.attrs()])
    search_base_users = LdapSearchBase(
        base_dn=ldap_server.users_ou(),
        filter='',
        name='users',
        )
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        )
    api.sync_ldap_users()
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    assert ldap_user.full_name == generated_ldap_user.full_name
    assert ldap_user.email == generated_ldap_user.email
    api.add_user_to_group(ldap_user.id, Groups.ADVANCED_VIEWERS)
    ldap_user_api = api.with_credentials(generated_ldap_user.uid, generated_ldap_user.password)
    assert ldap_user_api.credentials_work()
    assert len(ldap_user_api.list_cameras()) == cameras_count
    assert ldap_user_api.get_layout(layout_id) is None
    api.set_user_access_rights(ldap_user.id, [layout_id])
    assert ldap_user_api.get_layout(layout_id)
    # ffprobe uses a Digest auth scheme that is disabled by default on the server.
    api.switch_basic_and_digest_auth_for_ldap_user(ldap_user.id, True)
    with camera_server.async_serve():
        for camera in cameras:
            thumbnail = ldap_user_api.get_lightweight_camera_thumbnail(camera.id)
            assert thumbnail is not None
            assert data_is_jpeg_image(thumbnail)
            wait_for_stream(ldap_user_api.rtsp_url(camera.id))
    api.disable_user(ldap_user.id)
    try:
        ldap_user_api.credentials_work()
    except Forbidden as e:
        assert 'This user has been disabled by a ' in str(e)
    else:
        raise Exception("Disabled user should not be able to log in")
