# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os

if os.name == 'nt':
    from vm.virtual_box.run_as_user._windows_list_users import list_users
    from vm.virtual_box.run_as_user._windows_run_as_user import run_as_local_user
else:
    from vm.virtual_box.run_as_user._linux_list_users import list_users
    from vm.virtual_box.run_as_user._linux_run_as_user import run_as_local_user

__all__ = [
    'list_users',
    'run_as_local_user',
    ]
