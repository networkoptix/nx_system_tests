# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from arms.mikrotik_switch_api import MikrotikRESTApi

poe_switch = MikrotikRESTApi.from_url("http://admin:WellKnownPassword2@192.168.10.4:80")
