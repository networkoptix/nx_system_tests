# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_invalid_layout_type_id__ import _test_invalid_layout_type_id


class test_ubuntu22_v2(VMSTest):
    """Test invalid layout type id.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_invalid_layout_type_id(args.distrib_url, 'ubuntu22', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2().main())
