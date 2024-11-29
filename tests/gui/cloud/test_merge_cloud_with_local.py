# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import CloudTest
from tests.base_test import VMSTest


class test_merge_cloud_with_local(VMSTest, CloudTest):
    """Cloud system cannot be merged with local system.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6322

    Selection-Tag: 6322
    Selection-Tag: cloud
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        cloud_account_factory = make_cloud_account_factory(args.cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())

        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm_local, server_vm_cloud, client_installation] = exit_stack.enter_context(
            machine_pool.setup_local_server_cloud_server_client(
                args.cloud_host,
                cloud_user,
                ),
            )
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm_local),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm_local,
            )
        hid = HID(testkit_api)
        server_vm_cloud_info = server_vm_cloud.api.get_server_info()
        other_site_node = ResourceTree(testkit_api, hid).wait_for_other_site(server_vm_cloud_info.site_name)
        other_site_node.get_external_server(server_vm_cloud_info.server_name).activate_merge()
        msg_box = MessageBox(testkit_api, hid)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            msg_box.wait_until_has_label('Failed to merge  to our site.')
            assert msg_box.has_text('Cloud Site can only be merged with non-Cloud')
        else:
            msg_box.wait_until_has_label('Failed to merge  to our system.')
            assert msg_box.has_text('Cloud System can only be merged with non-Cloud')


if __name__ == '__main__':
    exit(test_merge_cloud_with_local().main())
