"""Owned interactive external tool; cancellation terminates its complete process tree."""
from __future__ import annotations
import threading
import queue

from .processes import run_bounded

class ToolSession:
    def __init__(self,command,*,cwd,log_path,environment,on_done,timeout=86400,interactive=False,on_output=None):
        self.cancel=threading.Event()
        self.input=queue.Queue(16) if interactive else None
        self.thread=threading.Thread(target=self._run,name='pcide-external-tool',daemon=False,
            args=(command,cwd,log_path,environment,on_done,timeout,on_output))
        self.thread.start()

    def _run(self,command,cwd,log_path,environment,on_done,timeout,on_output):
        error=''
        try:run_bounded(command,cwd=cwd,log_path=log_path,environment=environment,cancel=self.cancel,timeout=timeout,
                        input_lines=self.input,on_output=on_output)
        except Exception as exc:error=str(exc)
        finally:
            if self.input is not None:
                while not self.input.empty():
                    try:self.input.get_nowait()
                    except queue.Empty:break
            on_done({'ok':not error,'error':error,'log':str(log_path)})

    def send(self,line):
        if self.input is None or not self.active:raise RuntimeError('当前工具未打开控制台输入')
        if not isinstance(line,str) or len(line)>4096 or any(char in line for char in '\r\n\x00'):
            raise ValueError('单次输入应为不含换行/空字符的4096字符以内文本')
        try:self.input.put_nowait(line)
        except queue.Full:raise RuntimeError('控制台输入队列已满，请等待程序处理') from None

    def stop(self):self.cancel.set()
    def wait(self,timeout=5):self.thread.join(timeout);return not self.thread.is_alive()
    @property
    def active(self):return self.thread.is_alive()
