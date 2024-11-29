# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Manager
from typing import Iterable


class MachineNotFound(Exception):
    pass


class TaskQueue:

    def __init__(self, names: Iterable[str]):
        self._manager = Manager()
        self._queues = {name: SharedQueue(self._manager) for name in names}

    def get_queue(self, name: str):
        try:
            return self._queues[name]
        except KeyError:
            raise MachineNotFound(f"Machine {name} is not found")


class SharedQueue:
    _queue_method_names = [
        'qsize',
        'empty',
        'full',
        'put',
        'put_nowait',
        'get',
        'get_nowait',
        'close']

    def __init__(self, manager: Manager, maxsize: int = 10000):
        self._queue = manager.Queue(maxsize=maxsize)
        self._real_executor = None
        self._cancelled_join = False

    @property
    def _executor(self):
        # Executor is being implemented as a property
        # since we can't pickle ThreadPoolExecutor, so before
        # pickling (Which is used to run inside a process), we
        # set _real_executor to None
        if not self._real_executor:
            self._real_executor = ThreadPoolExecutor(max_workers=1)
        return self._real_executor

    def __getstate__(self):
        self_dict = self.__dict__
        self_dict['_real_executor'] = None
        return self_dict

    def __getattr__(self, name):
        if name in self._queue_method_names:
            return getattr(self._queue, name)
        else:
            raise AttributeError(f"{self.__class__} object has no attribute {name}")

    async def async_get(self):
        return await asyncio.get_running_loop().run_in_executor(self._executor, self.get)

    async def async_put(self, item):
        return await asyncio.get_running_loop().run_in_executor(self._executor, self.put, item)

    # join_thread used
    # at garbage collection,
    # so we should close thread pool at exit.
    def cancel_join_thread(self):
        self._cancelled_join = True
        self._queue.cancel_join_thread()

    def join_thread(self):
        self._queue.join_thread()
        if self._real_executor and not self._cancelled_join:
            self._real_executor.shutdown()
