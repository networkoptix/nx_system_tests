# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_playback_from_middle__ import _test_playback_from_middle


class test_win11_v0(VMSTest):
    """Test playback from middle.

    See: https://networkoptix.atlassian.net/browse/FT-325
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_playback_from_middle(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
