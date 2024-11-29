# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import NamedTuple
from typing import Optional
from uuid import UUID

from mediaserver_api._base_queue import BaseQueue
from mediaserver_api._base_resource import BaseResource


class EventQueue(BaseQueue):
    """Event queue for `api/getEvents`."""

    def __init__(
            self,
            api,
            wait_for_start_server=True,
            ):
        super().__init__()
        self._api = api
        if wait_for_start_server:
            # 5 seconds is enough for waiting start event, usually the mediaserver sends
            # the event immediately after start, but on ARM devices it can take 3-4 seconds.
            event = self.wait_for_next(timeout_sec=5)
            event_type = event.event_type
            if event_type != EventType.SERVER_START:
                raise RuntimeError(f"Got {event_type}, instead of expected {EventType.SERVER_START}")

    class EventRecord(NamedTuple):
        rule_id: UUID
        action_type: str
        event_type: str
        resource_id: Optional[UUID]
        resource_name: Optional[str]
        caption: Optional[str]
        description: Optional[str]
        action_url: Optional[str]
        event_date: datetime
        reason_code: str
        aggregation_count: int

    def _make_record(self, record_data):
        resource_id = record_data["eventParams"].get("eventResourceId")
        event_date = datetime.fromtimestamp(
            int(record_data['eventParams']['eventTimestampUsec']) / 10**6, tz=timezone.utc)
        return self.EventRecord(
            rule_id=UUID(record_data["businessRuleId"]),
            action_type=record_data["actionType"],
            event_type=record_data["eventParams"]["eventType"],
            resource_id=UUID(resource_id) if resource_id else None,
            resource_name=record_data["eventParams"].get("resourceName"),
            caption=record_data["eventParams"].get("caption"),
            description=record_data['eventParams'].get('description'),
            action_url=record_data["actionParams"].get("url"),
            event_date=event_date,
            reason_code=record_data['eventParams'].get('reasonCode'),
            aggregation_count=record_data['aggregationCount'],
            )

    def _load_events(self):
        # `from` is mandatory parameter
        return self._api.http_get('api/getEvents', {'from': 0})


class Rule(BaseResource):
    _event_descriptions = {
        'backupFinishedEvent': 'On Archive Backup Finished',
        'cameraDisconnectEvent': 'On Camera Disconnected',
        'cameraIpConflictEvent': 'On Camera IP Conflict',
        'userDefinedEvent': 'On Generic Event',
        'licenseIssueEvent': 'On License Issue',
        'networkIssueEvent': 'On Network Issue',
        'pluginDiagnosticEvent': 'On Plugin Diagnostic Event',
        'serverConflictEvent': 'On Server Conflict',
        'serverFailureEvent': 'On Server Failure',
        'serverStartEvent': 'On Server Started',
        'storageFailureEvent': 'On Storage Issue',
        'cameraMotionEvent': 'On Motion on Camera',
        'serverCertificateError': 'On Server Certificate Error',
        'ldapSyncIssueEvent': 'On LDAP Sync Issue',
        'serviceDisabledEvent': 'On Service disabled',
        'saasIssueEvent': 'On Services Issue',
        }
    _action_descriptions = {
        'sendMailAction': 'Send email',
        'showPopupAction': 'Show desktop notification',
        'diagnosticsAction': 'Write to log',
        'showTextOverlayAction': 'Show text overlay',
        'pushNotificationAction': 'Send mobile notification',
        }
    _event_type_by_description = {
        desc: type
        for type, desc in _event_descriptions.items()
        }
    _action_type_by_description = {
        desc: type
        for type, desc in _action_descriptions.items()
        }

    def __init__(self, data: dict):
        super().__init__(data, resource_id=UUID(data['id']))
        self.data = data
        self.data['actionParams'] = json.loads(data['actionParams'])
        self.data['eventCondition'] = json.loads(data['eventCondition'])
        self.event = self.data['eventType']
        self.action = self.data['actionType']
        self.state = EventState(self.data['eventState'])
        self._action_params = data['actionParams']
        self._action_resource_ids = [UUID(r_id) for r_id in data['actionResourceIds']]
        self._aggregation_period = data['aggregationPeriod']
        self._comment = data['comment']
        self._event_condition = data['eventCondition']
        self._event_resource_ids = [UUID(r_id) for r_id in data['eventResourceIds']]
        self._is_disabled = data['disabled']
        self._schedule = data['schedule']
        self._system = data['system']

    def __repr__(self):
        return f"<Rule: \"{self.event} --> {self.action}\">"

    @classmethod
    def _list_compared_attributes(cls):
        return [
            'action',
            '_action_params',
            '_action_resource_ids',
            '_aggregation_period',
            '_comment',
            'event',
            '_event_condition',
            '_event_resource_ids',
            '_is_disabled',
            'state',
            '_schedule',
            '_system',
            ]

    @staticmethod
    def parse_audit_record_params(params):
        # Description is taken from api/auditLog 'params' field.
        [_, description_text] = params.split('=')
        [event_text, action_text] = description_text.split('  --> ')
        return (
            Rule._event_type_by_description[event_text],
            Rule._action_type_by_description[action_text],
            )


class EventCondition:

    def __init__(
            self,
            resource_name="",
            omit_db_logging=False,
            params=None,
            ):
        if params is None:
            params = {}
        self._data = {
            "eventTimestampUsec": "0",
            "eventType": EventType.UNDEFINED,
            "metadata": {"allUsers": False},
            "reasonCode": "none",
            "resourceName": resource_name,
            "omitDbLogging": omit_db_logging,
            **params,
            }

    def to_string(self):
        return json.dumps(self._data)


class RuleAction:
    # TODO: Find out if defaults are needed at all.
    default_params = {
        'allUsers': False,
        'authType': 'authBasicAndDigest',
        'durationMs': 5000,
        'forced': True,
        'fps': 10,
        'needConfirmation': False,
        'playToClient': True,
        'recordAfter': 0,
        'recordBeforeMs': 1000,
        'streamQuality': 'highest',
        'useSource': False,
        }

    def __init__(self, type, resource_ids=(), params=None):
        if params is None:
            params = {}
        self.type = type
        self.params = params
        self.fields = {
            'actionType': type,
            'actionResourceIds': [*resource_ids],
            'actionParams': json.dumps({**self.default_params, **params}),
            }

    @classmethod
    def bookmark(cls, duration_ms, camera_ids):
        params = {'durationMs': duration_ms, 'recordBeforeMs': 0}
        return cls('bookmarkAction', resource_ids=camera_ids, params=params)

    @classmethod
    def http_request(cls, url, method=None, payload=None, auth_type='authBasicAndDigest'):
        params = {'url': str(url), 'authType': auth_type}
        if method is not None:
            params['httpMethod'] = method
        if payload is not None:
            params['text'] = payload.decode('utf8')
        return cls('execHttpRequestAction', params=params)

    @classmethod
    def push_notification(
            cls, cloud_user_ids, title=None, description=None, add_device_name=False):
        params = {
            'additionalResources': [f'{{{user_id}}}' for user_id in cloud_user_ids],
            'useSource': add_device_name,
            }
        if title is not None:
            params['sayText'] = title
        if description is not None:
            params['text'] = description
        return cls('pushNotificationAction', params=params)

    @classmethod
    def push_notification_all_users(cls):
        return cls('pushNotificationAction', params={'allUsers': True})

    @classmethod
    def send_mail(cls, email):
        return cls(RuleActionType.SEND_MAIL, params={"emailAddress": email})

    @classmethod
    def record_for(cls, duration_sec: float, resource_ids: list):
        return cls(
            type=RuleActionType.CAMERA_RECORD,
            resource_ids=resource_ids,
            params={"durationMs": round(duration_sec * 1000)})


class HttpAction(RuleAction):

    def __init__(self, url, params: Optional[dict] = None):
        params = {} if params is None else params
        super().__init__(RuleActionType.EXEC_HTTP_REQUEST, params={'url': url, **params})


class RuleActionType:
    UNDEFINED = "undefinedAction"
    CAMERA_OUTPUT = "cameraOutputAction"
    BOOKMARK = "bookmarkAction"
    CAMERA_RECORD = "cameraRecordingAction"
    PANIC_RECORD = "panicRecordingAction"
    SEND_MAIL = "sendMailAction"
    DIAGNOSTIC = "diagnosticsAction"
    SHOW_POPUP = "showPopupAction"
    PLAY_SOUND = "playSoundAction"
    PLAY_SOUND_ONCE = "playSoundOnceAction"
    SAY_TEXT = "sayTextAction"
    EXEC_PTZ = "executePtzPresetAction"
    SHOW_TEXT_OVERLAY = "showTextOverlayAction"
    SHOW_ON_ALARM_LAYOUT = "showOnAlarmLayoutAction"
    EXEC_HTTP_REQUEST = "execHttpRequestAction"
    ACKNOWLEDGE = "acknowledgeAction"


class EventType:
    ANALYTICS_SDK = 'analyticsSdkEvent'
    ANALYTICS_OBJECT_DETECTED = 'analyticsSdkObjectDetected'
    ANY = 'anyEvent'
    ANY_CAMERA = 'anyCameraEvent'
    ANY_SERVER = 'anyServerEvent'
    BACKUP_FINISHED = 'backupFinishedEvent'
    CAMERA_DISCONNECT = 'cameraDisconnectEvent'
    CAMERA_INPUT = 'cameraInputEvent'
    CAMERA_IP_CONFLICT = 'cameraIpConflictEvent'
    CAMERA_MOTION = 'cameraMotionEvent'
    LICENSE_ISSUE = 'licenseIssueEvent'
    MAX_SYSTEM_HEALTH = 'maxSystemHealthEvent'
    NETWORK_ISSUE = 'networkIssueEvent'
    PLUGIN = 'pluginEvent'
    PLUGIN_DIAGNOSTIC_EVENT = 'pluginDiagnosticEvent'
    SERVER_CONFLICT = 'serverConflictEvent'
    SERVER_FAILURE = 'serverFailureEvent'
    SERVER_START = 'serverStartEvent'
    SOFTWARE_TRIGGER = 'softwareTriggerEvent'
    STORAGE_FAILURE = 'storageFailureEvent'
    SYSTEM_HEALTH = 'systemHealthEvent'
    UNDEFINED = 'undefinedEvent'
    USER_DEFINED = 'userDefinedEvent'


class EventState(Enum):
    UNDEFINED = 'Undefined'
    ACTIVE = 'Active'
    INACTIVE = 'Inactive'
