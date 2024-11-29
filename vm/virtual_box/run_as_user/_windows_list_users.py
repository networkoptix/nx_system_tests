# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import subprocess
from typing import Collection


def list_users() -> Collection[str]:
    process = subprocess.run(['cmd.exe', '/c', 'net', 'user'], check=True, capture_output=True)
    lines = process.stdout.decode('utf8', errors='backslashreplace').splitlines()
    users = []
    while True:
        line = lines.pop()
        if line.startswith('---'):
            break
        elif not line:
            continue
        elif line == 'The command completed successfully.':
            continue
        else:
            users.extend(line.split())
    return users


if __name__ == '__main__':
    print(list_users())
