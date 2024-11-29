# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from infrastructure.message_broker import MessageBroker


def get_service_client() -> MessageBroker:
    return MessageBroker('127.0.0.1', 'ft_infra', 'WellKnownPassword2')


def get_default_client() -> MessageBroker:
    return MessageBroker('sc-ft003.nxlocal', 'ft_infra', 'WellKnownPassword2')


def get_monitoring_client() -> MessageBroker:
    return MessageBroker('sc-ft003.nxlocal', 'ft_monitoring', 'WellKnownPassword2')
