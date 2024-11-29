# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Windows Event Log.

It's a separate module because it's quite a large amount of code and because
it could be used not only in the course of a test but also as post-processing.
"""
import logging
from xml.etree import cElementTree as et

from os_access._windows_access import WindowsAccess


def clear_event_log(windows_access: WindowsAccess):
    _run_for_each_log(
        windows_access,
        _windows_event_logs,
        'WEvtUtil clear-log "%i"',
        )
    _run_for_each_log(
        windows_access,
        _applications_and_services_logs_by_os_version(windows_access),
        'WEvtUtil set-log "%i" /enabled:false',
        'WEvtUtil clear-log "%i"',
        'WEvtUtil set-log "%i" /enabled:true /quiet',
        )


def download_event_log(windows_access: WindowsAccess, target_local_dir):
    # Some debug and analytic logs must be disabled before querying events.
    _run_for_each_log(
        windows_access,
        _windows_event_logs + _applications_and_services_logs_by_os_version(windows_access),
        'WEvtUtil set-log "%i" /enabled:false',
        )
    # /format:RenderedXML is the only way to get textual messages. Events
    # themselves store just a message code, for which WEvtUtil gets
    # a corresponding message from the Windows internals. Unfortunately,
    # sometimes Windows cannot make a message.
    # All the logs come into a single file because it's usually not obvious
    # which log to examine. A single file is also easier to process.
    # TODO: Take Channel name from ./Event/System/Channel.
    output = _run_for_each_log(
        windows_access,
        _windows_event_logs + _applications_and_services_logs_by_os_version(windows_access),
        'echo ^<File^>',
        'echo ^<Name^>%i^</Name^>',
        'WEvtUtil query-events "%i" /format:RenderedXML /element:Events',
        'echo ^</File^>',
        )
    file_name = 'eventLog.xml'
    target_local_dir.joinpath(file_name).write_bytes(output)
    xml_ns = 'http://schemas.microsoft.com/win/2004/08/events/event'
    decoded_output = output.decode('windows-1252')
    root_elem = et.fromstringlist(['<root>', decoded_output, '</root>'])
    _channel_ranking = []
    _failed_channels = []
    for channel_elem in root_elem:
        channel_name = channel_elem.find('./Name').text
        event_list_elem = channel_elem.find('./Events')
        if event_list_elem is None:
            _failed_channels.append(channel_name)
            continue
        count = sum(1 for _ in event_list_elem)
        _channel_ranking.append((count, channel_name))
        for event_elem in event_list_elem:
            channel_name_elem = event_elem.find(
                './e:System/e:Channel', namespaces={'e': xml_ns})
            if channel_name != channel_name_elem.text:
                raise RuntimeError("Inconsistent Windows event logs XML")
    _channel_ranking.sort(reverse=True)
    if _failed_channels:
        _logger.error(
            "Event channels that failed, "
            "try disabling them before querying:\n"
            "    %s",
            '\n    '.join(_failed_channels))
    _logger.debug(
        "Event count per channel, "
        "many events - long downloading:\n"
        "    %s",
        '\n    '.join([f'{n}: {c}' for c, n in _channel_ranking]))


def _applications_and_services_logs_by_os_version(windows_access: WindowsAccess):
    [major, minor, *_] = windows_access._version()
    os_version_short_str = f'{major}.{minor}'
    logs = [
        name
        for [name, *versions] in _applications_and_services_logs
        if os_version_short_str in versions
        ]
    if not logs:
        raise RuntimeError(
            f"Can't find application and service logs for version {os_version_short_str}")
    return logs


def _run_for_each_log(windows_access: WindowsAccess, log_list, *commands):
    # A single command is used to avoid overhead of running a remote
    # command for each log, especially for empty logs.
    # A `for` loop is preferred over sub-commands sequenced with `&` to
    # minimize command length to work around the length limit of 8192.
    # '&' between commands for each iteration is used to maintain valid XML.
    joined = ' & '.join('@' + c for c in commands)
    result = windows_access.run(
        'for /f "usebackq delims=" %i in (`more`) do ' + joined,
        input='\n'.join(log_list).encode(), timeout_sec=300)
    return result.stdout


_windows_event_logs = ['System', 'Setup', 'Security']
_applications_and_services_logs = [
    # WMI.
    ('Microsoft-Windows-WMI-Activity/Operational', '6.3', '10.0'),
    # ('Microsoft-Windows-WMI-Activity/Trace', '6.3', '10.0'),  # Each call and more.

    # Startup tasks.
    # ('Microsoft-Windows-Shell-Core/Diagnostic', '6.3', '10.0'),

    # Services.
    ('Microsoft-Windows-Services/Diagnostic', '6.3', '10.0'),

    # Network.
    ('Microsoft-Windows-NetworkProfile/Operational', '6.3', '10.0'),  # NIC private/public.
    # ('Microsoft-Windows-Winsock-NameResolution/Operational', '6.3', '10.0'),  # DNS.
    # ('Microsoft-Windows-Winsock-AFD/Operational', '6.3', '10.0'),  # Net activity.
    # ('Microsoft-Windows-TCPIP/Diagnostic', '6.3', '10.0'),  # IP settings, net activity.
    ('Microsoft-Windows-TCPIP/Operational', '6.3', '10.0'),  # Usually empty.

    # SMB.
    ('Microsoft-Windows-SmbClient/Audit', '10.0'),
    ('Microsoft-Windows-SmbClient/Connectivity', '6.3', '10.0'),
    ('Microsoft-Windows-SmbClient/Diagnostic', '6.3', '10.0'),
    ('Microsoft-Windows-SmbClient/Security', '6.3', '10.0'),
    ('Microsoft-Windows-SMBServer/Audit', '10.0'),
    # ('Microsoft-Windows-SMBServer/Analytic', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-SMBServer/Connectivity', '6.3', '10.0'),
    # ('Microsoft-Windows-SMBServer/Diagnostic', '6.3', '10.0'),  # Each packet.
    ('Microsoft-Windows-SMBServer/Operational', '6.3', '10.0'),
    # ('Microsoft-Windows-SMBServer/Performance', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-SMBServer/Security', '6.3', '10.0'),

    # Firewall.
    ('Microsoft-Windows-Base-Filtering-Engine-Connections/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-Base-Filtering-Engine-Resource-Flows/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-Windows Firewall With Advanced Security/ConnectionSecurity', '6.3', '10.0'),
    ('Microsoft-Windows-Windows Firewall With Advanced Security/ConnectionSecurityVerbose', '6.3', '10.0'),
    ('Microsoft-Windows-Windows Firewall With Advanced Security/Firewall', '6.3', '10.0'),
    ('Microsoft-Windows-Windows Firewall With Advanced Security/FirewallDiagnostics', '10.0'),
    ('Microsoft-Windows-Windows Firewall With Advanced Security/FirewallVerbose', '6.3', '10.0'),
    ('Microsoft-Windows-Firewall-CPL/Diagnostic', '6.3', '10.0'),

    # Updates.
    ('Microsoft-Windows-WUSA/Debug', '6.3', '10.0'),
    ('Microsoft-Windows-WindowsUpdateClient/Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-WindowsUpdateClient/Operational', '6.3', '10.0'),

    # Licensing.
    ('Microsoft-Client-Licensing-Platform/Admin', '10.0'),
    ('Microsoft-Client-Licensing-Platform/Debug', '10.0'),
    ('Microsoft-Client-Licensing-Platform/Diagnostic', '10.0'),
    ('Microsoft-WS-Licensing/Diagnostic', '6.3'),
    ('Microsoft-WS-Licensing/Debug', '6.3'),
    ('Microsoft-WS-Licensing/Admin', '6.3'),

    # Disks.
    ('Microsoft-Windows-VIRTDISK-Analytic', '10.0'),
    # ('Microsoft-Windows-Kernel-Disk/Analytic', '6.3', '10.0'),  # Too verbose.
    # ('Microsoft-Windows-Partition/Analytic', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Partition/Diagnostic', '10.0'),
    ('Microsoft-Windows-Storage-ATAPort/Admin', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-ATAPort/Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-ATAPort/Debug', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-ATAPort/Diagnose', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-ATAPort/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-ClassPnP/Admin', '6.3', '10.0'),
    # ('Microsoft-Windows-Storage-ClassPnP/Analytic', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-ClassPnP/Debug', '6.3', '10.0'),
    # ('Microsoft-Windows-Storage-ClassPnP/Diagnose', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-ClassPnP/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-Disk/Admin', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-Disk/Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-Disk/Debug', '6.3', '10.0'),
    # ('Microsoft-Windows-Storage-Disk/Diagnose', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-Disk/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-Storage-Storport/Admin', '6.3', '10.0'),
    # ('Microsoft-Windows-Storage-Storport/Analytic', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-Storport/Debug', '6.3', '10.0'),
    # ('Microsoft-Windows-Storage-Storport/Diagnose', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-Storport/Health', '10.0'),
    # ('Microsoft-Windows-Storage-Storport/Operational', '6.3', '10.0'),  # Too verbose.
    ('Microsoft-Windows-Storage-Tiering-IoHeat/Heat', '10.0'),
    ('Microsoft-Windows-Storage-Tiering/Admin', '10.0'),
    ('Microsoft-Windows-Storage-Tiering/Heat', '6.3'),
    ('Microsoft-Windows-StorageManagement/Debug', '10.0'),  # Disable before querying.
    ('Microsoft-Windows-StorageManagement/Operational', '10.0'),
    ('Microsoft-Windows-StorageSpaces-Driver/Diagnostic', '10.0'),
    ('Microsoft-Windows-StorageSpaces-Driver/Operational', '6.3', '10.0'),
    ('Microsoft-Windows-StorageSpaces-Driver/Performance', '10.0'),
    ('Microsoft-Windows-StorageSpaces-Driver/Analytic', '6.3'),
    ('Microsoft-Windows-StorageSpaces-ManagementAgent/WHC', '6.3', '10.0'),
    ('Microsoft-Windows-StorageSpaces-SpaceManager/Diagnostic', '10.0'),
    ('Microsoft-Windows-StorageSpaces-SpaceManager/Operational', '10.0'),
    ('Microsoft-Windows-USB-MAUSBHOST-Analytic', '10.0'),
    ('Microsoft-Windows-USB-UCX-Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-USB-USBHUB/Diagnostic', '6.3', '10.0'),
    ('Microsoft-Windows-USB-USBHUB3-Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-USB-USBPORT/Diagnostic', '6.3', '10.0'),
    ('Microsoft-Windows-USB-USBXHCI-Analytic', '6.3', '10.0'),
    ('Microsoft-Windows-USB-USBXHCI-Trustlet-Analytic', '10.0'),
    ('Microsoft-Windows-Volume/Diagnostic', '10.0'),
    ('Microsoft-Windows-VolumeControl/Performance', '6.3', '10.0'),
    ('Microsoft-Windows-HAL/Debug', '6.3', '10.0'),  # Hardware abstraction layer.
    ]

_logger = logging.getLogger(__name__)
