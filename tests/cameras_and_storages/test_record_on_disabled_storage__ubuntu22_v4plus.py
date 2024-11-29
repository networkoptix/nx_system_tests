# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_record_on_disabled_storage__ import _test_record_on_disabled_storage


class test_ubuntu22_v4plus(VMSTest):
    """Test record on disabled storage.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_record_on_disabled_storage(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
