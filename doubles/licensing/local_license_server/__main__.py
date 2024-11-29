# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from doubles.licensing.local_license_server import LocalLicenseServer


def main():
    logging.basicConfig(level=logging.DEBUG)
    license_server = LocalLicenseServer()
    with license_server.serving():
        while True:
            time.sleep(600)


if __name__ == '__main__':
    main()
