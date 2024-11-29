# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Collection


def list_users() -> Collection[str]:
    import pwd
    return [record.pw_name for record in pwd.getpwall()]


if __name__ == '__main__':
    print(list_users())
