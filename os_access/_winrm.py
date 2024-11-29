# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import base64
import logging
import pprint
import socket
import threading
import xml
from contextlib import closing
from datetime import datetime
from datetime import timezone
from http.client import HTTPConnection
from pprint import pformat
from typing import Any
from typing import Mapping
from typing import NamedTuple
from typing import NoReturn
from typing import Optional
from typing import Union
from uuid import uuid4
from xml.dom import minidom
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ParseError
from xml.etree.ElementTree import XML
from xml.etree.ElementTree import tostring

import xmltodict

_logger = logging.getLogger(__name__)

_xml_namespace_aliases = {
    # Those namespaces (URIs) are fixed and used in requests and responses, while aliases are
    # arbitrary. To make it easier to understand the code, some are taken from
    # examples in WMI documentation.
    # TODO: Use aliases from WS-Management spec.
    # See: Table A-1 in https://www.dmtf.org/sites/default/files/standards/documents/DSP0226_1.0.0.pdf  # noqa
    'http://www.w3.org/XML/1998/namespace': 'xml',
    'http://www.w3.org/2003/05/soap-envelope': 'env',
    'http://schemas.xmlsoap.org/ws/2004/09/enumeration': 'n',
    'http://www.w3.org/2001/XMLSchema-instance': 'xsi',
    'http://www.w3.org/2001/XMLSchema': 'xs',
    'http://schemas.dmtf.org/wbem/wscim/1/common': 'cim',
    'http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd': 'w',
    'http://schemas.dmtf.org/wbem/wsman/1/cimbinding.xsd': 'b',
    'http://schemas.xmlsoap.org/ws/2004/09/transfer': 't',
    'http://schemas.xmlsoap.org/ws/2004/08/addressing': 'a',
    'http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd': 'p',
    'http://schemas.microsoft.com/wbem/wsman/1/windows/shell': 'rsp',
    'http://schemas.microsoft.com/wbem/wsman/1/config': 'cfg',
    'http://schemas.microsoft.com/wbem/wsman/1/wsmanfault': 'fault',
    'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/MSFT_WmiError': 'cim_error',
    'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/microsoft/windows/storage/MSFT_WmiError': 'storage_cim_error',
    'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/__ExtendedStatus': 'extended_status',
    'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/standardcimv2/MSFT_WmiError': 'network_cim_error',
    }
_xml_aliases = {a: n for n, a in _xml_namespace_aliases.items()}

# Explanation: https://docs.microsoft.com/en-us/windows/desktop/WmiSdk/wmi-error-constants.
# More: https://docs.microsoft.com/en-us/windows/desktop/adsi/win32-error-codes.
_win32_error_codes = {
    # Errors originating in the core operating system.
    # Remove 0x8007, lookup for last 4 hex digits.
    # See: https://docs.microsoft.com/en-us/windows/desktop/debug/system-error-codes
    0x80071392: 'ERROR_OBJECT_ALREADY_EXISTS',
    # WBEM Errors.
    # See: https://docs.microsoft.com/en-us/windows/desktop/WmiSdk/wmi-error-constants
    0x80041005: 'WBEM_E_TYPE_MISMATCH',
    0x80041008: 'WBEM_E_INVALID_PARAMETER',
    }

STATUS_CONTROL_C_EXIT = 0xC000013A  # See: https://msdn.microsoft.com/en-us/library/cc704588.aspx


class WinRMOperationTimeoutError(Exception):
    """WinRM-level operation timeout (not a connection-level timeout).

    This is an expected outcome that should be retried transparently
    by the client when waiting for output from a long-running process.
    """

    pass


class WinRmHttpResponseTimeout(Exception):
    pass


class WinRmUnauthorized(Exception):
    pass


def resolve_resource_uri(short_uri):
    """Resolve namespace alias or find right namespace for a class.

    In WS-Man calls, a full URI is required. But classes are usually referred
    to in the internet only by names, which are quite unique. That's why
    namespaces are likely to clutter client code.
    """
    if '//' in short_uri:
        return short_uri
    if '/' in short_uri:
        alias, rest = short_uri.split('/', 1)
        return _winrm_aliases[alias] + '/' + rest
    if short_uri.startswith('Win32_'):
        return _winrm_aliases['wmicimv2'] + '/' + short_uri
    raise ValueError(
        f"Cannot guess namespace of {short_uri}; "
        f"Win32_ classes are unambiguous: they all in one namespace; "
        f"MSFT_ classes are distributed across several namespaces")


def _xml_bits(uri):
    [directory, name] = uri.rsplit('/', 1)
    # The URI must be in some "canonical" letter case form, because
    # the way the code works with XML now is not entirely correct.
    uri = directory.lower() + '/' + name
    ns = _xml_namespace_aliases.get(uri, uri)
    assert ns, "Empty alias (default namespace) must not be used globally"
    tag = ns + ':' + name
    return ns, tag


class _OptionSet:

    def __init__(self, raw, as_dict):
        self.raw = raw
        self.as_dict = as_dict

    def __repr__(self):
        return '_OptionSet.from_dict({!r})'.format(self.as_dict)

    def __eq__(self, other):
        if not isinstance(other, _OptionSet):
            return NotImplemented
        return other.as_dict == self.as_dict

    @classmethod
    def from_dict(cls, as_dict):
        elements = []
        for name, value in as_dict.items():
            if isinstance(value, str):
                elements.append({'@Name': name, '#text': value})
            else:
                raise RuntimeError("Unsupported option: {}".format(value))
        return cls({'w:Option': elements}, as_dict)

    @classmethod
    def from_raw(cls, raw):
        as_dict = {}
        for elem in raw['w:Option']:
            if '#text' in elem:
                as_dict[elem['@Name']] = elem['#text']
            else:
                raise ValueError("Cannot understand option: {}".format(elem))
        return cls(raw, as_dict)

    @classmethod
    def empty(cls):
        return cls.from_dict({})


def _prepare_data(data):
    if data is None:
        return {'@xsi:nil': 'true'}
    if data == '':
        return None
    if isinstance(data, datetime):
        if data.tzinfo is None:
            raise ValueError(
                "If ISO datetime passed in XML has no timezone, "
                "it's interpreted by Windows as UTC, not as the local timezone.")
        return {'cim:Datetime': data.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
    if isinstance(data, dict):
        return {key: _prepare_data(data[key]) for key in data}
    return data


def _parse_data(data):
    if data is None:
        return ''
    if data == {'@xsi:nil': 'true'}:
        return None
    if isinstance(data, dict):
        if 'cim:Datetime' in data:
            formats = ['%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z']
            raw = data['cim:Datetime']
            for f in formats:
                try:
                    parsed = datetime.strptime(raw, f)
                except ValueError:
                    _logger.debug("Parse %s with %s: try next", raw, f)
                else:
                    _logger.debug("Parse %s with %s: %s", raw, f, parsed)
                    return parsed
            raise ValueError(f"Cannot parse {raw} with formats {formats}")
        return {key: _parse_data(data[key]) for key in data}
    return data


# See `winrm help aliases`.
_winrm_aliases = {
    'wmi': 'http://schemas.microsoft.com/wbem/wsman/1/wmi',
    'wmicimv2': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2',
    'cimv2': 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2',
    'winrm': 'http://schemas.microsoft.com/wbem/wsman/1',
    'wsman': 'http://schemas.microsoft.com/wbem/wsman/1',
    'shell': 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell',
    }


class Reference(NamedTuple):
    uri: str
    selectors: Mapping[str, Union[str, Reference, None]]


def _parse_ref(raw):
    wmi_class = raw['a:ReferenceParameters']['w:ResourceURI']
    # `SelectorSet` isn't always present, e.g. with `Win32_OperatingSystem`.
    if 'w:SelectorSet' in raw['a:ReferenceParameters']:
        selector_set = _parse_selector_set(raw['a:ReferenceParameters']['w:SelectorSet'])
    else:
        selector_set = {}
    return Reference(wmi_class, selector_set)


def _selectors_from_dict(as_dict):
    if not as_dict:
        return {}
    elements = []
    for name, value in as_dict.items():
        if isinstance(value, str):
            elements.append({'@Name': name, '#text': value})
        elif isinstance(value, Reference):
            elements.append({'@Name': name, 'a:EndpointReference': _ref_from_selectors(*value)})
        elif value is None:
            elements.append({'@Name': name})
        else:
            raise RuntimeError("Unsupported selector: {}".format(value))
    return {'w:Selector': elements}


def _ref_from_selectors(uri, selectors):
    return {
        'a:Address': 'http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous',
        'a:ReferenceParameters': {
            'w:ResourceURI': uri,
            'w:SelectorSet': _selectors_from_dict(selectors),
            },
        }


def _parse_selector_set(raw):
    as_dict = {}
    for elem in raw['w:Selector']:
        if '#text' in elem:
            as_dict[elem['@Name']] = elem['#text']
        elif 'a:EndpointReference' in elem:
            as_dict[elem['@Name']] = _parse_ref(elem['a:EndpointReference'])
        elif set(elem.keys()).issubset({'@xmlns', '@Name'}):
            as_dict[elem['@Name']] = None
        else:
            raise ValueError("Cannot understand selector: {}".format(elem))
    return as_dict


def _single_object_from_outcome(uri, outcome):
    [namespace, tag] = _xml_bits(uri)
    for tag, data in outcome.items():
        if tag.lower() == tag.lower():
            return _format_data(namespace, data)
    raise KeyError(f"Cannot find {tag} in {outcome}")


def _format_data(namespace, data):
    res = {}
    for key, value in _parse_data(data).items():
        if key == '@xmlns' or key == '@xsi:type':
            continue
        assert key.startswith(namespace + ':')
        attr = key[len(namespace) + 1:]
        if isinstance(value, dict):
            if 'a:ReferenceParameters' in value:
                res[attr] = _parse_ref(value)
                continue
        res[attr] = value
    return res


class WmiInvokeFailed(Exception):

    def __init__(self, cls, selectors, method, params, return_value: int, method_output):
        if return_value & 0x80000000:
            error_text = _win32_error_codes.get(return_value, 'unknown')
            return_value_formatted = f'0x{return_value:X} ({error_text})'
        else:
            return_value_formatted = str(return_value)
        super().__init__(
            'Non-zero return value {} of {!s}.{!s}({!r}) where {!r}:\n{!s}'.format(
                return_value_formatted,
                cls,
                method,
                params,
                selectors,
                pformat(method_output),
                ))
        self.return_value: int = return_value


# See: https://docs.microsoft.com/en-us/previous-versions/windows/desktop/ramgmtpsprov/msft-wmierror
class WmiError(Exception):
    INVALID_PARAMETER = 4
    NOT_FOUND = 6
    ALREADY_EXISTS = 11

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f'Error code {self.code}: {message}')


class WmiObjectNotFound(Exception):
    """WMI object is not found. Usually handled to the application level."""

    def __init__(self, operation: str, parameter_info: str, provider_name: str):
        self.operation = operation
        self.parameter_info = parameter_info
        self.provider_name = provider_name


class SoapFault(Exception):

    def __init__(self, message: str, code_ns: str, code_value: str):
        super().__init__(message)
        self.code_ns = code_ns
        self.code_value = code_value


class WmiFault(Exception):

    def __init__(self, wmi_fault_element):
        super().__init__(wmi_fault_element.text)


class BadSelectors(Exception):

    def __init__(self, message: str, code_ns: str):
        super().__init__(message)
        self.code_ns = code_ns


class WinRM:
    """Windows-specific interface.

    WinRM has only generic functions.
    WinRM must not know of particular WMI classes and CMD and PowerShell scripts.
    """

    def __init__(self, address, port, username, password):
        self._address: str = address
        self._port: int = port
        user_pass = (username.encode() + b':' + password.encode())
        self._auth = b'Basic ' + base64.b64encode(user_pass)
        self._repr = f'WinRM({address!r}, {port!r}, {username!r}, password)'
        self._lock = threading.Lock()

    def __repr__(self):
        return self._repr

    def netloc(self):
        return f'{self._address}:{self._port}'

    def _request(self, data: bytes):
        # Windows terminates TCP connection after 120 seconds without requests.
        # A corresponding setting has not been found yet. Reconnect only once
        # and only if the connection is explicitly closed by Windows.
        _logger.debug("%s: connect", self)
        with closing(
                HTTPConnection(self._address, self._port, timeout=150)) as connection:
            self._send_request(connection, data)
            response = self._read_response(connection)
            response_type = response.headers.get('Content-Type', 'text/plain')
            content = response.read()
            return response.status, response_type, content

    def _send_request(self, connection, data):
        try:
            connection.request(
                'POST',
                '/wsman',
                body=data,
                headers={
                    'Content-Type': 'application/soap+xml;charset=UTF-8',
                    'Authorization': self._auth,
                    },
                )
        except socket.gaierror as e:
            if e.errno == -2:
                raise RuntimeError(
                    f"DNS server responded that {self._address} is not known to it")
            raise

    @staticmethod
    def _read_response(connection):
        try:
            # TODO: Make sure that timing out here is normal.
            return connection.getresponse()
        except TimeoutError:
            raise WinRmHttpResponseTimeout()

    def _handle_500_http_error(self, content: bytes) -> NoReturn:
        if not content:
            raise RuntimeError(
                "Error 500 with empty body; "
                "may be caused by the disabling of unencrypted traffic; "
                "check: `winrm g winrm/config/service`; "
                "fix: `winrm s winrm/config/service @{AllowUnencrypted=\"true\"}`")
        try:
            root: Element = XML(content)
        except ParseError:
            raise RuntimeError(f"Can't decode WinRM message:\n{content}")
        soap_fault = root.find('env:Body/env:Fault', _xml_aliases)
        if soap_fault is None:
            raise RuntimeError(f"WinRM error:\n{tostring(root)}")
        wsmanfault_code = soap_fault.find('env:Detail/fault:WSManFault[@Code]', _xml_aliases)
        if wsmanfault_code is not None:  # If exists, handle error_code
            error_code = int(wsmanfault_code.get('Code'))
            if error_code == 0x80338000:
                fault_message_xpath = "env:Detail/fault:WSManFault/fault:Message"
                fault_message = soap_fault.find(fault_message_xpath, _xml_aliases)
                status_xpath = "fault:ProviderFault/fault:ExtendedError/extended_status:__ExtendedStatus"
                extended_status = fault_message.find(status_xpath, _xml_aliases)
                operation = extended_status.find("extended_status:Operation", _xml_aliases)
                parameter_info = extended_status.find("extended_status:ParameterInfo", _xml_aliases)
                provider_name = extended_status.find("extended_status:ProviderName", _xml_aliases)
                raise WmiObjectNotFound(operation.text, parameter_info.text, provider_name.text)
            elif error_code == 0x80338029:
                raise WinRMOperationTimeoutError()
        wmi_fault = soap_fault.find(
            'env:Detail/fault:WSManFault/fault:Message/fault:ProviderFault/fault:WSManFault/fault:Message',
            _xml_aliases)
        if wmi_fault is not None:
            raise WmiFault(wmi_fault)
        for ns in ['cim_error', 'storage_cim_error', 'network_cim_error']:
            cim_error = soap_fault.find(f'env:Detail/{ns}:MSFT_WmiError', _xml_aliases)
            if cim_error is not None:
                code = int(cim_error.find(f'{ns}:CIMStatusCode', _xml_aliases).text)
                message = cim_error.find(f'{ns}:Message', _xml_aliases).text
                raise WmiError(code, message)

        message_elem = soap_fault.find('env:Reason/env:Text', _xml_aliases)
        [message] = message_elem.itertext()
        code_elem = soap_fault.find('env:Code/env:Subcode', _xml_aliases)
        [code_full] = code_elem.itertext()
        code_ns_alias, code_value = code_full.split(':', 1)
        code_ns = _xml_aliases[code_ns_alias]
        if code_value == 'InvalidSelectors':
            raise BadSelectors(message=message, code_ns=code_ns)
        raise SoapFault(message=message, code_ns=code_ns, code_value=code_value)

    def _handle_http_errors(self, status: int, content: bytes) -> NoReturn:
        if status == 401:
            raise WinRmUnauthorized(f"{self}: unauthorized")
        elif status == 404:
            if not content:
                raise RuntimeError(
                    "Error 404 with empty body; "
                    "check IP settings on the NIC the request goes through "
                    "or reboot")
        elif status == 500:
            self._handle_500_http_error(content)  # Handler is too big to keep it here
        raise RuntimeError(f"Unexpected status {status}")

    def act(
            self,
            class_uri: str,
            action: str,
            body: Mapping[str, Any],
            selectors: Mapping[str, Any],
            options: Optional[_OptionSet] = None,
            timeout_sec: Optional[float] = None) -> Optional[Mapping[str, Any]]:
        options = options or _OptionSet.empty()
        operation_timeout_sec = timeout_sec or 120
        message_id = 'uuid:' + str(uuid4())
        rq = {
            'env:Envelope': {
                **{'@xmlns:' + alias: uri for uri, alias in _xml_namespace_aliases.items()},
                'env:Header': {
                    'a:To': 'http://windows-host:5985/wsman',  # Hostname may be any.
                    'a:ReplyTo': {
                        'a:Address': {
                            'http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous',
                            },
                        },
                    'a:MessageID': message_id,
                    'w:ResourceURI': {'@env:mustUnderstand': 'true', '#text': class_uri},
                    'a:Action': {'@env:mustUnderstand': 'true', '#text': action},
                    'w:MaxEnvelopeSize': {'@env:mustUnderstand': 'true', '#text': str(64 * 1024 * 1024)},
                    'w:OperationTimeout': 'PT{:06.3f}S'.format(operation_timeout_sec),
                    # WinRM can't guarantee the locales and fails, hence mustUnderstand="false".
                    'w:Locale': {'@env:mustUnderstand': 'false', '@xml:lang': 'en-US'},
                    'p:DataLocale': {'@env:mustUnderstand': 'false', '@xml:lang': 'en-US'},
                    **({'w:OptionSet': options.raw} if options.as_dict else {}),
                    **({'w:SelectorSet': _selectors_from_dict(selectors)}),
                    },
                'env:Body': body,
                },
            }
        request_xml = xmltodict.unparse(rq, pretty=True, indent='  ')
        _logger.debug("Request:\n%s", request_xml)
        with self._lock:
            status, response_type, content = self._request(request_xml.encode('utf-8'))
        try:
            response_dom = minidom.parseString(content)
        except xml.parsers.expat.ExpatError:
            response_pretty = content
        else:
            response_pretty = response_dom.toprettyxml(indent='  ')
        _logger.debug(
            "Response (%s, %d bytes):\n%s",
            response_type, len(content),
            response_pretty,
            )

        if status != 200:
            self._handle_http_errors(status, content)

        response_dict = xmltodict.parse(
            content,
            process_namespaces=True,
            namespaces=_xml_namespace_aliases,  # Force namespace aliases.
            force_list=['w:Item', 'w:Selector', 'rsp:Stream'],
            )
        # Ensure the response relates to request
        relates_to = response_dict['env:Envelope']['env:Header']['a:RelatesTo']
        if relates_to != message_id:
            raise RuntimeError("Unexpected RelatesTo {}: for MessageId {}".format(relates_to, message_id))
        return response_dict['env:Envelope']['env:Body']

    def enumerate(self, resource_uri, raw_filter, max_elements=32000):
        enumeration_context = [None]
        enumeration_is_ended = [False]

        def _start():
            _logger.info("Start enumerating %s with filter: %r", resource_uri, raw_filter)
            assert not enumeration_is_ended[0]
            action = 'http://schemas.xmlsoap.org/ws/2004/09/enumeration/Enumerate'
            body = {
                'n:Enumerate': {
                    'w:OptimizeEnumeration': None,
                    'w:MaxElements': str(max_elements),
                    # Set mode as `EnumerateObjectAndEPR` to get selector set for reference and
                    # be able to invoke methods on returned object.
                    # See: Paragraph 8.7 in https://www.dmtf.org/sites/default/files/standards/documents/DSP0226_1.0.0.pdf  # noqa
                    'w:EnumerationMode': 'EnumerateObjectAndEPR',
                    **raw_filter,
                    },
                }
            response = self.act(resource_uri, action, body, {})
            enumeration_context[0] = response['n:EnumerateResponse']['n:EnumerationContext']
            enumeration_is_ended[0] = 'w:EndOfSequence' in response['n:EnumerateResponse']
            try:
                items_elem = response['n:EnumerateResponse']['w:Items']
            except KeyError:
                # Enumerate request (enumeration start) may or may not contain Items.
                # See: https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-wsmv/b79bcdd9-125c-49e0-8a4f-bac4ce878592  # noqa
                return []
            items = items_elem['w:Item']
            return _pick_objects(items)

        def _pull():
            _logger.info("Continue enumerating %s with filter: %r", resource_uri, raw_filter)
            assert enumeration_context[0] is not None
            assert not enumeration_is_ended[0]
            action = 'http://schemas.xmlsoap.org/ws/2004/09/enumeration/Pull'
            body = {
                'n:Pull': {
                    'n:EnumerationContext': enumeration_context[0],
                    'n:MaxElements': str(max_elements),
                    },
                }
            response = self.act(resource_uri, action, body, {})
            enumeration_is_ended[0] = 'n:EndOfSequence' in response['n:PullResponse']
            if enumeration_is_ended[0]:
                enumeration_context[0] = None
            else:
                enumeration_context[0] = response['n:PullResponse']['n:EnumerationContext']
            items = response['n:PullResponse']['n:Items']['w:Item']
            return _pick_objects(items)

        def _pick_objects(item_list):
            # `EnumerationMode` must be `EnumerateObjectAndEPR` to have both data and selectors.
            obj_list = []
            for item in item_list:
                ref = _parse_ref(item['a:EndpointReference'])
                # Use the reference URI, it may be selected by the base class.
                [xml_ns, xml_tag] = _xml_bits(ref.uri)
                data = item[xml_tag]
                obj = _format_data(xml_ns, data)
                obj_list.append((ref, obj))
            _logger.debug("Objects in enumeration:\n%s", pprint.pformat(obj_list))
            return obj_list

        for item in _start():
            yield item
        while not enumeration_is_ended[0]:
            for item in _pull():
                yield item

    def wsman_create(self, cls, properties_dict):
        _logger.info("Create %r: %r", cls, properties_dict)
        action_url = 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Create'
        uri = resolve_resource_uri(cls)
        *_, name = uri.split('/')
        body = {name: _prepare_data(properties_dict)}
        body[name]['@xmlns'] = uri
        outcome = self.act(uri, action_url, body, {})
        ref = _parse_ref(outcome['t:ResourceCreated'])
        if ref.uri.lower() != uri.lower():
            raise RuntimeError("Created URI is not the requested")
        return ref

    def wsman_get(self, cls, selectors):
        _logger.info("Get %s where %r", cls, selectors)
        action_url = 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Get'
        uri = resolve_resource_uri(cls)
        outcome = self.act(uri, action_url, {}, selectors)
        return _single_object_from_outcome(uri, outcome)

    def wsman_put(self, cls, selectors, new_properties_dict):
        _logger.info("Put %s where %r: %r", cls, selectors, new_properties_dict)
        action_url = 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Put'
        uri = resolve_resource_uri(cls)
        *_, name = uri.split('/')
        body = {name: _prepare_data(new_properties_dict)}
        body[name]['@xmlns'] = uri
        outcome = self.act(uri, action_url, body, selectors)
        return _single_object_from_outcome(uri, outcome)

    def wsman_delete(self, cls, selectors):
        _logger.info("Delete %s where %r", cls, selectors)
        action_url = 'http://schemas.xmlsoap.org/ws/2004/09/transfer/Delete'
        uri = resolve_resource_uri(cls)
        self.act(uri, action_url, {}, selectors)

    def wsman_invoke(
            self,
            cls: str,
            selectors: Mapping[str, Any],
            method_name: str,
            params: Mapping[str, Any],
            timeout_sec: Optional[float] = None) -> Optional[Mapping[str, Any]]:
        """Invoke a method of a WMI object.

        `params` may be empty if the method has no parameters.
        It should still be provided explicitly though,
        like a Python method or function call with empty parentheses.
        """
        [_, _, cls_name] = cls.rpartition('/')
        _logger.info("Invoke %s.%s(%r) where %r", cls_name, method_name, params, selectors)
        uri = resolve_resource_uri(cls)
        action_uri = uri + '/' + method_name
        method_input = {'p:' + param_name: param_value for param_name, param_value in _prepare_data(params).items()}
        method_input['@xmlns:p'] = uri
        method_input['@xmlns:cim'] = 'http://schemas.dmtf.org/wbem/wscim/1/common'  # For `cWMIim:Datetime`.
        method_input['@xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'  # For `@xsi:nil`.
        body = {method_name + '_INPUT': method_input}
        response = self.act(uri, action_uri, body, selectors, timeout_sec=timeout_sec)
        [xml_ns, _xml_tag] = _xml_bits(uri)
        output_raw = response[xml_ns + ':' + method_name + '_OUTPUT']
        if output_raw is None:
            # Some methods return no output. MSFT_NetFirewallRule.Disable is of this kind,
            # although, according to documentation, it returns uint32. Data is parsed afterwards,
            # because _parse_data would return empty string.
            return None
        method_output = _parse_data(output_raw)
        return_value = method_output[xml_ns + ':ReturnValue']
        if return_value not in ['0', None]:
            raise WmiInvokeFailed(cls, selectors, method_name, params, int(return_value), method_output)
        return method_output

    def wsman_all(self, cls):
        uri = resolve_resource_uri(cls)
        return self.enumerate(uri, {})

    def wsman_select(self, cls, selectors):
        uri = resolve_resource_uri(cls)
        return self.enumerate(uri, {
            'w:Filter': {
                '@Dialect': 'http://schemas.dmtf.org/wbem/wsman/1/wsman/SelectorFilter',
                'w:SelectorSet': _selectors_from_dict(selectors),
                },
            })

    def wsman_associations(
            self,
            cls, selectors,
            association_cls_name=None, source_field=None):
        uri = resolve_resource_uri(cls)
        return self.enumerate(uri.rsplit('/', 1)[0] + '/*', {
            'w:Filter': {
                '@Dialect': 'http://schemas.dmtf.org/wbem/wsman/1/cimbinding/associationFilter',
                'b:AssociationInstances': {
                    'b:Object': _ref_from_selectors(uri, selectors),
                    'b:ResultClassName': association_cls_name,
                    'b:Role': source_field,
                    },
                },
            })

    def wsman_associated(
            self,
            cls, selectors,
            association_cls_name=None, result_cls_name=None,
            source_field=None, destination_field=None):
        uri = resolve_resource_uri(cls)
        return self.enumerate(uri.rsplit('/', 1)[0] + '/*', {
            'w:Filter': {
                '@Dialect': 'http://schemas.dmtf.org/wbem/wsman/1/cimbinding/associationFilter',
                'b:AssociatedInstances': {
                    'b:Object': _ref_from_selectors(uri, selectors),
                    'b:AssociationClassName': association_cls_name,
                    'b:ResultClassName': result_cls_name,
                    'b:Role': source_field,
                    'b:ResultRole': destination_field,
                    },
                },
            })

    def wsman_wql(self, short_all_classes_uri, query):
        all_classes_uri = resolve_resource_uri(short_all_classes_uri)
        assert all_classes_uri.endswith('/*')  # DSP0227 1.0.0, 6.2.
        return self.enumerate(all_classes_uri, {
            'w:Filter': {
                '@Dialect': 'http://schemas.microsoft.com/wbem/wsman/1/WQL',
                '#text': query,
                },
            })
