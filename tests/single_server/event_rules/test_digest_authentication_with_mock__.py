# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import HttpAction
from mediaserver_api import calculate_digest
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event
from tests.single_server.event_rules.common import http_server
from tests.single_server.event_rules.common import url_for


def _test_digest_authentication_with_mock(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    uri = '/api/createEvent?arbitrary_param=arbitrary_value'
    user = 'arbitrary_user'
    password = 'arbitrary_password'
    httpserver = exit_stack.enter_context(http_server())
    url = url_for(
        httpserver.port,
        mediaserver.os_access.source_address(),
        uri,
        f'{user}:{password}',
        )
    nonce = 'constant_value_that_must_be_random_in_real_life'
    realm = 'Network Optix Mediaserver mock'
    with event(mediaserver.api, HttpAction(url, {'authDigest': 'authBasic'})):
        www_authenticate_headers = {
            'WWW-Authenticate': (
                f'Digest realm={_quote(realm)}, '
                f'nonce={_quote(nonce)}, '
                f'algorithm="MD5"'),
            }
        with httpserver.wait() as request:
            request.respond('401 Unauthorized', www_authenticate_headers)
        response = calculate_digest('GET', uri, realm, nonce, user, password)
        auth_values = (
            f'username={_quote(user)}, '
            f'realm={_quote(realm)}, '
            f'nonce={_quote(nonce)}, '
            f'uri={_quote(uri)}, '
            f'response={_quote(response)}, '
            'algorithm="MD5"')
        with httpserver.wait() as request:
            assert request.header('Authorization') == f'Digest {auth_values}'


def _quote(value):
    if '"' in value:
        raise ValueError("Quotes in header values are not allowed")
    return '"' + value + '"'
