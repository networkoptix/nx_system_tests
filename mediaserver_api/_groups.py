# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class UserGroup(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self.name = raw_data['name']
        self.permissions = set(raw_data['permissions'].split('|'))
        self.permissions.discard('none')

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name} {self.id}, parameters: {self.raw_data}>'


class GroupV3(UserGroup):

    def __init__(self, raw_data):
        super().__init__(raw_data)
        self.is_ldap = raw_data['type'] == 'ldap'
        self.parent_group_ids = set([UUID(group_id) for group_id in raw_data['parentGroupIds']])

    def synced(self):
        if self.is_ldap:
            return self.raw_data['externalId']['synced']
        else:
            raise RuntimeError('Only LDAP groups can be synced')


class Groups:
    ADMIN = UUID('00000000-0000-0000-0000-100000000000')
    POWER_USERS = UUID('00000000-0000-0000-0000-100000000001')
    ADVANCED_VIEWERS = UUID('00000000-0000-0000-0000-100000000002')
    VIEWERS = UUID('00000000-0000-0000-0000-100000000003')
    LIVE_VIEWERS = UUID('00000000-0000-0000-0000-100000000004')
    HEALTH_VIEWERS = UUID('00000000-0000-0000-0000-100000000005')
    LDAP_DEFAULT = UUID('00000000-0000-0000-0000-100100000000')
