# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import Fleet
from provisioning import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master


def main():
    fl = Fleet.compose([
        sc_ft003_master,
        sc_ft,
        ])
    fl.run([
        Run('sudo mkdir -p /tmp/tcpdump'),
        Run('sudo chmod a+rwX /tmp/tcpdump'),
        Run('sudo -u ft ln -fs /tmp/tcpdump ~ft/.cache/'),
        Run('sudo start-stop-daemon --pidfile /tmp/tcpdump/pid --start --oknodo --background --make-pidfile --startas /usr/bin/tcpdump -- -vn -W14 -G $((60*60*24)) -w /tmp/tcpdump/"dns-%Y%m%d.pcap" "udp and port 53"'),
        ])
    fl.run([
        # Run('sudo start-stop-daemon --pidfile /tmp/tcpdump/pid --stop --oknodo'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    raise SystemExit(main())
