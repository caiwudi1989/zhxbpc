from pcide.runtime_api import tasks
import threading
ready=threading.Event()
def work(cancel): ready.set(); return 42
with tasks.pool(workers=1,capacity=2) as p:
    job=p.submit(work)
    print(ready.wait(2),job.result(2))
