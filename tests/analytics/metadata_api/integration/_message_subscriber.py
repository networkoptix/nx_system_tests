# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from queue import Queue
from typing import Any
from typing import Hashable


class _MessageSubscriber:

    def __init__(self):
        self._subscriptions: dict[Hashable, list[Queue]] = {}

    def notify(
            self,
            message: Any,
            subscription_id: Hashable,
            ):
        subscriptions = self._subscriptions.get(subscription_id, [])
        for subscription in subscriptions:
            subscription.put_nowait(message)

    def subscribe(self, id_: Hashable):
        existing_subscriptions = self._subscriptions.setdefault(id_, [])
        subscription = Queue()
        existing_subscriptions.append(subscription)
        return subscription

    def __repr__(self):
        return f"<{self.__class__.__name__} with {len(self._subscriptions)} subscriptions>"
