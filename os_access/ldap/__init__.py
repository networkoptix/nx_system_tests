# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import pathlib
import socket
from contextlib import contextmanager

import asn1tools

_logger = logging.getLogger(__name__)


# Partial ASN1 LDAP message schema to encode/decode LDAP messages using ASN1.
# Full schema is not needed for now. To get full schema check links below.
# https://cwiki.apache.org/confluence/display/DIRxSRVx10/Ldap+ASN.1+Codec
# https://ldapwiki.com
_ldap_asn_codec = asn1tools.compile_files([pathlib.Path(__file__).parent / 'ldap.asn'])

_LDAP_DEFAULT_PORT = 389


@contextmanager
def _ldap_connection(host):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ldap_sock:
        ldap_sock.settimeout(10)
        ldap_sock.connect((host, _LDAP_DEFAULT_PORT))
        _logger.debug("Connection to LDAP server (%s, %d) established", host, _LDAP_DEFAULT_PORT)
        yield ldap_sock


def _ldap_request(connection, message, await_response=True):
    _logger.debug("Sending message %r", message)
    message = _ldap_asn_codec.encode('LDAPMessage', message)
    connection.send(message)
    if not await_response:
        return
    # This decoding flow works only if server respond with single fixed length
    # message. Server can respond with several LDAPMessage in one response (for
    # example in response of search request). To implement proper decoding
    # check https://www.itu.int/ITU-T/studygroups/com17/languages/X.690-0207.pdf section 8.
    response = connection.recv(8 * 1024**2)
    response_message = _ldap_asn_codec.decode('LDAPMessage', response)
    [_, response_data] = response_message['protocolOp']
    if response_data['resultCode'] != 'success':
        [request_operation, _] = message['protocolOp']
        error = response_data['errorMessage'].decode('utf8')
        raise RuntimeError(
            f"Operation {request_operation} failed: "
            f"result code: {response_data['resultCode']}; error: {error}")
    return response


def change_ldap_user_password(user_dn, new_password, admin_dn, admin_password, ldap_host):
    # Message ID should increment by one with every new message. There are only three of them, so
    # message ids are hardcoded to simplify code.
    with _ldap_connection(ldap_host) as connection:
        bind_message = {
            'messageID': 1,
            'protocolOp': ('bindRequest', {
                'name': admin_dn.encode('utf8'),
                'authentication': ('simple', admin_password.encode('utf8')),
                'version': 3})}
        _ldap_request(connection, bind_message)
        encoded_password = _ldap_asn_codec.encode('PasswdModifyRequestValue', {
            'userIdentity': user_dn.encode('utf8'), 'newPasswd': new_password.encode('utf8')})
        change_password_message = {
            'messageID': 2,
            'protocolOp': ('extendedReq', {
                'requestName': b'1.3.6.1.4.1.4203.1.11.1',  # passwdModifyOID
                'requestValue': encoded_password})}
        _ldap_request(connection, change_password_message)
        unbind_message = {'messageID': 3, 'protocolOp': ('unbindRequest', None)}
        _ldap_request(connection, unbind_message, await_response=False)
