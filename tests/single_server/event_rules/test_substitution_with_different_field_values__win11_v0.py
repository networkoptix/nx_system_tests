# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_substitution_with_different_field_values__ import _test_substitution_with_different_field_values


class test_win11_v0(VMSTest):
    """Test substitution with different field values.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/54185
    """

    def _run(self, args, exit_stack):
        _test_substitution_with_different_field_values(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
