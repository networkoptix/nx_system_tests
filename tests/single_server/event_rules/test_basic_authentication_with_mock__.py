# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from base64 import b64encode

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import HttpAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event
from tests.single_server.event_rules.common import http_server
from tests.single_server.event_rules.common import url_for


def _test_basic_authentication_with_mock(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    uri = '/api/createEvent?arbitrary_param=arbitrary_value'
    user = 'arbitrary_user'
    password = 'arbitrary_password'
    httpserver = exit_stack.enter_context(http_server())
    url = url_for(httpserver.port, server.os_access.source_address(), uri, f'{user}:{password}')
    base64value = b64encode(b'%b:%b' % (user.encode('utf8'), password.encode('utf8')))
    basic_auth_value = base64value.decode('utf8')
    with event(server.api, HttpAction(url, {'httpMethod': 'GET', 'authType': 'authBasic'})):
        with httpserver.wait() as request:
            assert request.header('Authorization') == f'Basic {basic_auth_value}'
