# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
from ipaddress import IPv4Address
from ipaddress import ip_address
from uuid import UUID

from mediaserver_api._cameras import CameraStatus
from mediaserver_api._cameras import MotionType

BASE_CAMERA_IP_ADDRESS = ip_address('192.168.0.0')
BASE_SERVER_IP_ADDRESS = ip_address('10.10.0.0')
BASE_STORAGE_IP_ADDRESS = ip_address('10.2.0.0')
CAMERA_SERVER_GUID_PREFIX = "ca14e2a0-8e25-e200-0000"
SERVER_GUID_PREFIX = "8e25e200-0000-0000-0000"
GROUP_GUID_PREFIX = "58e30000-0000-0000-0000"
STORAGE_GUID_PREFIX = "81012a6e-0000-0000-0000"
LAYOUT_GUID_PREFIX = "1a404100-0000-0000-0000"
LAYOUT_ITEM_GUID_PREFIX = "1a404100-11e1-1000-0000"
VIDEOWALL_GUID_PREFIX = "1a404200-0000-0000-0000"
VIDEOWALL_ITEM_GUID_PREFIX = "1a404200-0001-0000-0000"
PC_GUID_PREFIX = "1a404300-0000-0000-0000"
CAMERA_MAC_PREFIX = "ee-00-"


def _make_guid(prefix, index):
    return '{' + f'{prefix}-{index:012d}' + '}'


def generate_server_guid(index):
    guid = "%s-%012d" % (SERVER_GUID_PREFIX, index)
    return "{%s}" % guid


def _generate_mac(index):
    return CAMERA_MAC_PREFIX.upper() + "-".join(map(lambda n: "%02X" % (index >> n & 0xFF), [24, 16, 8, 0]))


def _generate_name(prefix, index):
    return "%s_%s" % (prefix, index)


def _generate_formatter_uuid(salt):
    return '{{{!s}}}'.format(UUID(bytes=hashlib.md5(salt).digest()))


def _generate_ip_v4(index, base_address):
    assert isinstance(base_address, IPv4Address)
    return str(base_address + index)


def _generate_ip_v4_endpoint(index):
    return "%s:7001" % _generate_ip_v4(index, BASE_SERVER_IP_ADDRESS)


def generate_camera(index, parent_id=None):
    mac = _generate_mac(index)
    camera_name = 'ft-test-cam-{:05d}'.format(index)
    return dict(
        audioEnabled=bool(index % 2),
        controlEnabled=index % 3,
        dewarpingParams="",
        groupId='',
        groupName='',
        id=_generate_formatter_uuid(mac.encode('ascii')),
        mac=mac,
        manuallyAdded=False,
        maxArchiveDays=0,  # vms_5.0 and earlier
        minArchiveDays=0,  # vms_5.0 and earlier
        maxArchivePeriodS=0,  # vms_5.0_patch
        minArchivePeriodS=0,  # vms_5.0_patch
        model=camera_name,
        motionMask='',
        motionType=str(MotionType.DEFAULT.value),
        name=camera_name,
        parentId=parent_id or _make_guid(CAMERA_SERVER_GUID_PREFIX, index),
        physicalId=mac,
        preferedServerId='{00000000-0000-0000-0000-000000000000}',
        scheduleEnabled=False,
        scheduleTasks=[],
        secondaryStreamQuality='SSQualityLow',
        status=CameraStatus.UNAUTHORIZED,
        statusFlags='CSF_NoFlags',
        typeId='{1b7181ce-0227-d3f7-9443-c86aab922d96}',
        # typeId='{774e6ecd-ffc6-ae88-0165-8f4a6d0eafa7}',
        url=_generate_ip_v4(index, BASE_CAMERA_IP_ADDRESS),
        vendor="NetworkOptix")


def generate_group(index, permissions):
    return dict(
        id=_make_guid(GROUP_GUID_PREFIX, index=index),
        permissions=permissions,
        name=f'Group{index}',
        )


def generate_mediaserver(index):
    server_address = _generate_ip_v4_endpoint(index)
    server_name = 'ft-mediaserver-{:04d}'.format(index)
    return dict(
        apiUrl=server_address,
        url='rtsp://%s' % server_address,
        authKey=_generate_formatter_uuid(server_name.encode('ascii')),
        flags='SF_HasPublicIP',
        id=generate_server_guid(index),
        name=server_name,
        networkAddresses=server_address,
        panicMode='PM_None',
        parentId='{00000000-0000-0000-0000-000000000000}',
        systemInfo='windows x64 win78',
        systemName=server_name,
        version='3.0.0.0',
        typeId='{be5d1ee0-b92c-3b34-86d9-bca2dab7826f}',
        osInfo={
            'platform': 'linux_x64',
            'variant': 'ubuntu',
            'variantVersion': '16.04',
            'flavor': 'default',
            },
        )


def generate_camera_user_attributes(camera):
    dewarping_params = '''{"enabled":false,"fovRot":0,
    "hStretch":1,"radius":0.5,"viewMode":"1","xCenter":0.5,"yCenter":0.5}'''
    return dict(
        audioEnabled=False,
        backupType='CameraBackupDefault',
        cameraId=camera['id'],
        cameraName=camera['name'],
        controlEnabled=True,
        dewarpingParams=dewarping_params,
        failoverPriority='Medium',
        licenseUsed=True,
        maxArchiveDays=-30,  # vms_5.0 and earlier
        minArchiveDays=-1,  # vms_5.0 and earlier
        maxArchivePeriodS=-30 * 24 * 60 * 60,  # vms_5.0_patch
        minArchivePeriodS=-1 * 24 * 60 * 60,  # vms_5.0_patch
        motionMask='5,0,0,44,32:5,0,0,44,32:5,0,0,44,32:5,0,0,44,32',
        motionType=str(MotionType.SOFTWARE.value),
        preferredServerId='{00000000-0000-0000-0000-000000000000}',
        scheduleEnabled=False,
        scheduleTasks=[],
        secondaryStreamQuality='SSQualityMedium',
        userDefinedGroupName='',
        )


def generate_storage(index, parent_id):
    return dict(
        id=_make_guid(STORAGE_GUID_PREFIX, index),
        name=_generate_name('Storage', index),
        # By default we use samba storage to avoid accidentally local storage creating
        url='smb://%s' % _generate_ip_v4(index, BASE_STORAGE_IP_ADDRESS),
        storageType='smb',
        usedForWriting=False,
        isBackup=False,
        parentId=parent_id,
        )


def generate_layout_item(index, resource_id):
    return dict(
        id=_make_guid(LAYOUT_ITEM_GUID_PREFIX, index),
        left=0.0, top=0.0, right=0.0, bottom=0.0,
        rotation=0.0,
        resourceId=resource_id,
        resourcePath='', zoomLeft=0, zoomTop=0, zoomRight=0,
        zoomBottom=0, zoomTargetId='{00000000-0000-0000-0000-000000000000}',
        displayInfo=False,
        )


def generate_layout(index, parent_id=None, items=()):
    default_layout_data = dict(
        id=_make_guid(LAYOUT_GUID_PREFIX, index=index),
        name='ft-layout-{:04d}'.format(index),
        fixedWidth=0,
        fixedHeight=0,
        items=[*items],
        )
    if parent_id is not None:
        default_layout_data['parentId'] = parent_id
    return default_layout_data


def generate_mediaserver_user_attributes(server):
    return dict(
        allowAutoRedundancy=False,
        maxCameras=200,
        serverId=server['id'],
        serverName=server['name'],
        backupType='BackupManual',
        backupDaysOfTheWeek='2',  # Monday
        backupStart=0,
        backupDuration=-1,
        backupBitrate=-1,
        )


def generate_resource_params(resource, list_size):
    if isinstance(resource, dict):
        resource_id = resource['id']
    else:
        resource_id = resource
    resource_params = {
        f'Resource_{resource_id}_{i}': f'Value_{resource_id}_{i}' for i in range(list_size)}
    return resource_params


def generate_videowall():
    return dict(
        id=_make_guid(VIDEOWALL_GUID_PREFIX, 0),
        name='ft-videowall',
        autorun=True,
        timeline=True,
        screens=[dict(
            pcGuid=_make_guid(PC_GUID_PREFIX, 0),
            pcIndex=0,
            desktopLeft=0,
            desktopTop=0,
            desktopWidth=0,
            desktopHeight=0,
            layoutLeft=0,
            layoutTop=0,
            layoutWidth=0,
            layoutHeight=0,
            )],
        items=[],
        matrices=[],
        )


def generate_videowall_with_items(videowall, layout_list):
    items = [
        dict(
            guid=_make_guid(VIDEOWALL_ITEM_GUID_PREFIX, index),
            name='ft-screen-{:03d}'.format(index),
            layoutGuid=layout['id'],
            pcGuid=videowall['screens'][0]['pcGuid'],
            )
        for index, layout in enumerate(layout_list or [])]
    return dict(
        id=videowall['id'],
        items=items,
        )
