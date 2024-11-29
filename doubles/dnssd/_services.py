# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket

from doubles.dnssd._common_types import Record
from doubles.dnssd._common_types import ServiceAdvertisement
from doubles.dnssd._record_types import ARecordData
from doubles.dnssd._record_types import PtrRecordData
from doubles.dnssd._record_types import SrvRecordData
from doubles.dnssd._record_types import TxtRecordData


class DNSSDWebService(ServiceAdvertisement):

    def __init__(self, name, local_address, port, path='/'):
        service_type = '_http._tcp.local.'
        target = name + '.' + service_type
        host = socket.gethostname() + '.local.'
        meta_query_name = '_services._dns-sd._udp.local.'  # RFC 6763, section 9.
        super().__init__([
            Record(target, TxtRecordData([f'path={path}'])),
            Record(service_type, PtrRecordData(target)),
            Record(target, SrvRecordData(host, port)),
            Record(host, ARecordData(local_address)),
            Record(meta_query_name, PtrRecordData(service_type)),
            ])
