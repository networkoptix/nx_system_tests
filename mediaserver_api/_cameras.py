# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import json
from abc import ABCMeta
from abc import abstractmethod
from enum import Enum
from enum import Flag
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class BaseCamera(BaseResource, metaclass=ABCMeta):
    """Make _Camera object from parsed server data."""

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self.group_id = self._group_id(raw_data)
        self.group_name = self._group_name(raw_data)
        self.physical_id = raw_data['physicalId']
        self.name = raw_data['name']
        self.url = raw_data['url']
        self.parent_id = self._parent_id(raw_data)
        self.status = raw_data.get('status')
        backup_type = self._backup_type(raw_data)
        self.backup_type = set(backup_type.split('|')) if backup_type else None
        backup_quality = self._backup_quality(raw_data)
        self.backup_quality = set(backup_quality.split('|')) if backup_quality else None
        self.backup_policy = self._backup_policy(raw_data)
        self.schedule_tasks = self._schedule_tasks(raw_data)
        self.schedule_is_enabled = self._schedule_is_enabled(raw_data)
        if raw_data['logicalId']:
            logical_id_raw_int = int(raw_data['logicalId'])
            if logical_id_raw_int >= 1:
                self.logical_id = logical_id_raw_int
            else:
                # Server keeps logical_ids < 1 although they cannot be used to access the camera
                self.logical_id = None
        else:
            # Logical id was never set
            self.logical_id = None
        self.preferred_server_id = self._preferred_server_id(raw_data)
        params = self._params(raw_data)
        self.stream_urls = params['streamUrls']
        self.primary_url = self.stream_urls.get('1') or self.url
        self.path = urlparse(self.primary_url).path
        self.secondary_url = self.stream_urls.get('2')
        if self.secondary_url is not None:
            self.secondary_path = urlparse(self.secondary_url).path
        else:
            self.secondary_path = None
        self.io_settings = _IoSettings(params['ioSettings'])
        self.ptz_capabilities = {
            name
            for name, flag in _PTZ_CAPABILITY_FLAGS.items()
            if params['ptzCapabilities'] & flag
            }
        self.has_capabilities = self._has_capabilities(raw_data)
        model = raw_data['model']
        vendor = raw_data['vendor']
        self.attributes = {
            'model': model,
            'firmware': params['firmware'],
            'vendor': vendor,
            'mac': raw_data['mac'],
            'ptzCapabilities': params['ptzCapabilities'],
            'url': self.url,
            }
        self.identity = f'{vendor}_{model}_{self.physical_id}'.replace(' ', '_')
        motion_type_raw = self._motion_type(raw_data)
        if motion_type_raw.isnumeric():
            self.motion_type = MotionType(int(motion_type_raw))
            if self.motion_type not in MotionType:
                raise RuntimeError(
                    f"Invalid motion type: {motion_type_raw!r} "
                    "(combined values are used to denote supported motion types)")
        else:
            self.motion_type = MotionType[motion_type_raw.upper()]
        self._dewarping_params = self._dewarping_params(raw_data)
        self._audio_is_enabled = self._audio_is_enabled(raw_data)
        self._control_is_enabled = self._control_is_enabled(raw_data)
        self._dual_streaming_is_disabled = self._dual_streaming_is_disabled(raw_data)
        self._license_is_used = self._license_is_used(raw_data)
        self._is_manually_added = self._is_manually_added(raw_data)
        self._failover_priority = self._failover_priority(raw_data)
        self._mac = raw_data['mac']
        self._model = raw_data['model']
        self._motion_mask = self._motion_mask(raw_data)
        self._parameters = self._params(raw_data)
        self._record_after_motion_sec = self._record_after_motion_sec(raw_data)
        self._record_before_motion_sec = self._record_before_motion_sec(raw_data)
        self._type_id = UUID(raw_data['typeId'])
        self._vendor = raw_data['vendor']
        if '//' in self.url:
            self.hostname = urlparse(self.url).hostname
        else:
            # If there's no "//", urlparse assumes a path, not a netloc.
            self.hostname = self.url

    def __repr__(self):
        return f'<_Camera {self.name} {self.physical_id} {self.url}>'

    @classmethod
    def _list_compared_attributes(cls):
        return [
            '_audio_is_enabled',
            'backup_policy',
            '_backup_quality',
            'backup_type',
            '_control_is_enabled',
            '_dewarping_params',
            '_dual_streaming_is_disabled',
            '_failover_priority',
            'group_id',
            'group_name',
            '_is_manually_added',
            '_license_is_used',
            'logical_id',
            '_mac',
            '_model',
            '_motion_mask',
            'motion_type',
            'name',
            '_parameters',
            'parent_id',
            'physical_id',
            'preferred_server_id',
            '_record_after_motion_sec',
            '_record_before_motion_sec',
            'schedule_is_enabled',
            'schedule_tasks',
            '_type_id',
            'url',
            '_vendor',
            ]

    @staticmethod
    @abstractmethod
    def _backup_policy(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _backup_quality(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _backup_type(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _group_id(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _group_name(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _parent_id(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _schedule_tasks(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _schedule_is_enabled(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _preferred_server_id(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _params(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _motion_type(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _dewarping_params(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _failover_priority(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _audio_is_enabled(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _control_is_enabled(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _dual_streaming_is_disabled(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _license_is_used(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _is_manually_added(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _motion_mask(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _record_after_motion_sec(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _record_before_motion_sec(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _has_capabilities(raw_data):
        pass


class RecordingType(Enum):
    ALWAYS = 'RT_Always'
    MOTION_ONLY = 'RT_MotionOnly'
    NEVER = 'RT_Never'
    MOTION_AND_LOW_QUALITY = 'RT_MotionAndLowQuality'

    @classmethod
    def _missing_(cls, missing_value: str) -> Optional[RecordingType]:
        # After VMS-30331, RecordingType values were renamed. Server still supports the old ones,
        # but only returns the new ones.
        alternative_values = {
            'always': cls.ALWAYS,
            'metadataOnly': cls.MOTION_ONLY,
            'never': cls.NEVER,
            'metadataAndLowQuality': cls.MOTION_AND_LOW_QUALITY,
            }
        return alternative_values.get(missing_value)


class CameraStatus:
    OFFLINE = "Offline"
    ONLINE = "Online"
    RECORDING = "Recording"
    UNAUTHORIZED = "Unauthorized"


class MotionType(Flag):
    DEFAULT = 0
    HARDWARE = 1
    SOFTWARE = 2
    WINDOW = 4
    NONE = 8


class _IoSettings:

    class _Pins:

        def __init__(self):
            self._pins = {}

        @property
        def ids(self):
            return list(self._pins.keys())

        def get_name(self, pin_id):
            return self._pins.get(pin_id)

        def add(self, pin_id, name):
            self._pins[pin_id] = name

    def __init__(self, raw_settings):
        self.inputs = self._Pins()
        self.outputs = self._Pins()
        for pin in raw_settings:
            if pin['portType'] == 'Input':
                self.inputs.add(pin['id'], pin['inputName'])
            else:
                self.outputs.add(pin['id'], pin['outputName'])


_PTZ_CAPABILITY_FLAGS = {
    'presets': 0x10000,
    'absoluteRotation': 0x40000000,
    'absolutePan': 0x00000010,
    'absoluteTilt': 0x00000020,
    'absoluteZoom': 0x00000040,
    }
PTZ_CAPABILITIES = _PTZ_CAPABILITY_FLAGS.keys()


class _CameraV0(BaseCamera):

    def __init__(self, raw_data):
        super().__init__(raw_data)
        status_flags = raw_data['statusFlags']
        self._status_flags = set(status_flags.split('|'))
        self._user_defined_group_name: str = raw_data['userDefinedGroupName']

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = ['_status_flags', '_user_defined_group_name']
        return base_attributes + version_specific_attributes

    @staticmethod
    def _backup_policy(raw_data):
        return raw_data.get('backupPolicy')

    @staticmethod
    def _backup_quality(raw_data):
        return raw_data.get('backupQuality')

    @staticmethod
    def _backup_type(raw_data):
        return raw_data.get('backupType')

    @staticmethod
    def _group_id(raw_data):
        return raw_data['groupId']

    @staticmethod
    def _group_name(raw_data):
        return raw_data['groupName']

    @staticmethod
    def _parent_id(raw_data):
        return UUID(raw_data['parentId'])

    @staticmethod
    def _schedule_tasks(raw_data):
        return raw_data['scheduleTasks']

    @staticmethod
    def _schedule_is_enabled(raw_data):
        return raw_data['scheduleEnabled']

    @staticmethod
    def _preferred_server_id(raw_data):
        return UUID(raw_data['preferredServerId'])

    @staticmethod
    def _params(raw_data):
        parameters = {p['name']: p['value'] for p in raw_data['addParams']}
        parameters['compatibleAnalyticsEngines'] = json.loads(
            parameters.get('compatibleAnalyticsEngines', '[]'))
        parameters['firmware'] = parameters.get('firmware')
        parameters['ioSettings'] = json.loads(parameters.get('ioSettings', '[]'))
        parameters['mediaCapabilities'] = json.loads(parameters.get('mediaCapabilities', '{}'))
        parameters['ptzCapabilities'] = int(parameters.get('ptzCapabilities', '0'))
        parameters['streamUrls'] = json.loads(parameters.get('streamUrls', '{}'))
        return parameters

    @staticmethod
    def _motion_type(raw_data):
        return raw_data['motionType']

    @staticmethod
    def _dewarping_params(raw_data):
        return raw_data['dewarpingParams']

    @staticmethod
    def _failover_priority(raw_data):
        return raw_data['failoverPriority']

    @staticmethod
    def _audio_is_enabled(raw_data):
        return raw_data['audioEnabled']

    @staticmethod
    def _control_is_enabled(raw_data):
        return raw_data['controlEnabled']

    @staticmethod
    def _dual_streaming_is_disabled(raw_data):
        return raw_data['disableDualStreaming']

    @staticmethod
    def _license_is_used(raw_data):
        return raw_data['licenseUsed']

    @staticmethod
    def _is_manually_added(raw_data):
        return raw_data['manuallyAdded']

    @staticmethod
    def _motion_mask(raw_data):
        return raw_data['motionMask']

    @staticmethod
    def _record_after_motion_sec(raw_data):
        return raw_data['recordAfterMotionSec']

    @staticmethod
    def _record_before_motion_sec(raw_data):
        return raw_data['recordBeforeMotionSec']

    @staticmethod
    def _has_capabilities(raw_data):
        for param in raw_data['addParams']:
            if param['name'] == 'cameraCapabilities':
                return param['value'] != '0'
        return False


class CameraV1(BaseCamera):

    @staticmethod
    def _backup_policy(raw_data):
        return raw_data['options'].get('backupPolicy')

    @staticmethod
    def _backup_quality(raw_data):
        return raw_data['options'].get('backupQuality')

    @staticmethod
    def _backup_type(raw_data):
        return raw_data['options']['backupContentType']

    @staticmethod
    def _group_id(raw_data):
        return raw_data.get('group', {}).get('id')

    @staticmethod
    def _group_name(raw_data):
        return raw_data.get('group', {}).get('name')

    @staticmethod
    def _parent_id(raw_data):
        return UUID(raw_data['serverId'])

    @staticmethod
    def _schedule_tasks(raw_data):
        return raw_data['schedule']['tasks']

    @staticmethod
    def _schedule_is_enabled(raw_data):
        return raw_data['schedule']['isEnabled']

    @staticmethod
    def _preferred_server_id(raw_data):
        return UUID(raw_data['options']['preferredServerId'])

    @staticmethod
    def _params(raw_data):
        parameters = raw_data['parameters']
        parameters.setdefault('firmware', None)
        parameters.setdefault('ioSettings', [])
        ptz_capabilities = parameters.get('ptzCapabilities')
        parameters['ptzCapabilities'] = int(ptz_capabilities) if ptz_capabilities else 0
        parameters.setdefault('streamUrls', {})
        return parameters

    @staticmethod
    def _motion_type(raw_data):
        return raw_data['motion']['type']

    @staticmethod
    def _dewarping_params(raw_data):
        return raw_data['options']['dewarpingParams']

    @staticmethod
    def _failover_priority(raw_data):
        return raw_data['options']['failoverPriority']

    @staticmethod
    def _audio_is_enabled(raw_data):
        return raw_data['options']['isAudioEnabled']

    @staticmethod
    def _control_is_enabled(raw_data):
        return raw_data['options']['isControlEnabled']

    @staticmethod
    def _dual_streaming_is_disabled(raw_data):
        return raw_data['options']['isDualStreamingDisabled']

    @staticmethod
    def _license_is_used(raw_data):
        return raw_data['isLicenseUsed']

    @staticmethod
    def _is_manually_added(raw_data):
        return raw_data['isManuallyAdded']

    @staticmethod
    def _motion_mask(raw_data):
        return raw_data['motion']['mask']

    @staticmethod
    def _record_after_motion_sec(raw_data):
        return raw_data['motion']['recordAfterS']

    @staticmethod
    def _record_before_motion_sec(raw_data):
        return raw_data['motion']['recordBeforeS']

    @staticmethod
    def _has_capabilities(raw_data):
        return raw_data['capabilities'] != 'noCapabilities'
