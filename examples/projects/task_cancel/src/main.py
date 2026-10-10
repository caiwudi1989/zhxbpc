from pcide.runtime_api import tasks
import threading
started=threading.Event()
def work(cancel):
    started.set()
    while tasks.sleep(cancel,0.01): pass
    return "cancelled"
with tasks.pool(workers=1,capacity=2) as p:
    job=p.submit(work)
    started.wait(2); job.cancel()
    print(job.result(2))
