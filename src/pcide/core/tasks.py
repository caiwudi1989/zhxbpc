"""Worker-owned cooperative tasks with bounded queue, lifetime and result retention."""
from __future__ import annotations

import math
import queue
import threading
import time
import weakref
from concurrent.futures import Future

_POOLS = weakref.WeakSet()
_REGISTRY_LOCK = threading.Lock()

class TaskHandle:
    def __init__(self):
        self.future = Future()
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()
        return self.future.cancel()

    def result(self, timeout=30):
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise ValueError('等待超时应为 0..3600 秒')
        return self.future.result(timeout)

    def done(self):
        return self.future.done()

class TaskPool:
    def __init__(self, workers=2, capacity=16):
        if type(workers) is not int or not 1 <= workers <= 4 or type(capacity) is not int or not workers <= capacity <= 64:
            raise ValueError('工作线程应为 1..4，总容量应为线程数..64')
        self.queue = queue.Queue(capacity)
        self.slots = threading.BoundedSemaphore(capacity)
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.handles = set()
        with _REGISTRY_LOCK:
            if len(_POOLS) >= 4:
                raise RuntimeError('每个脚本宿主最多 4 个任务池')
            _POOLS.add(self)
        self.threads = [threading.Thread(target=self._worker, name='pcide-library-task', daemon=False) for _ in range(workers)]
        for thread in self.threads:
            thread.start()

    def submit(self, function, *args, **kwargs):
        if not callable(function):
            raise ValueError('任务必须是函数，首个参数为取消事件')
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError('任务池已关闭')
            if not self.slots.acquire(blocking=False):
                raise RuntimeError('任务容量已满；请先等待或取消已有任务')
            handle = TaskHandle()
            self.handles.add(handle)
            self.queue.put_nowait((handle, function, args, kwargs))
            return handle

    def _worker(self):
        while not self.closed.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            handle, function, args, kwargs = item
            try:
                if handle.future.set_running_or_notify_cancel():
                    try:
                        result = function(handle.cancel_event, *args, **kwargs)
                        handle.future.set_result(result)
                        del result
                    except BaseException as exc:
                        handle.future.set_exception(exc)
            finally:
                with self.lock:
                    self.handles.discard(handle)
                self.slots.release()
                self.queue.task_done()
                # Drop callable/argument references before waiting for work.
                del item, handle, function, args, kwargs

    def close(self, timeout=3):
        if type(timeout) not in {int, float} or not math.isfinite(timeout) or not 0 < timeout <= 10:
            raise ValueError('关闭等待应为 0..10 秒')
        with self.lock:
            self.closed.set()
            for handle in tuple(self.handles):
                handle.cancel()
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            if thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))
        if any(thread.is_alive() for thread in self.threads):
            raise RuntimeError('任务未响应取消；独立脚本宿主的超时/停止将回收进程')
        with _REGISTRY_LOCK:
            _POOLS.discard(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

def pool(workers=2, capacity=16):
    return TaskPool(workers, capacity)

def sleep(cancel, seconds):
    if not isinstance(cancel, threading.Event) or type(seconds) not in {int, float} or not math.isfinite(seconds) or not 0 <= seconds <= 3600:
        raise ValueError('需要任务取消事件和 0..3600 秒时长')
    return not cancel.wait(seconds)

def close_all():
    with _REGISTRY_LOCK:
        pools = list(_POOLS)
    for value in pools:
        value.close()
