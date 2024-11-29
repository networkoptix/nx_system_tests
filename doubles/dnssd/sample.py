# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Advertise HTTP service via mDNS/DNS-SD according to RFC 6763."""
from doubles.dnssd._scope import DNSSDScope
from doubles.dnssd._services import DNSSDWebService

if __name__ == '__main__':
    _mdns_multicast = DNSSDScope([('224.0.0.251', 5353)])
    _mdns_multicast.advertise_in_foreground([DNSSDWebService('mpjpeg2', '10.0.0.34', 12312, '/1.mjpeg')])
