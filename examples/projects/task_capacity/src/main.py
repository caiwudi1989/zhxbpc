from pcide.runtime_api import tasks
import threading
started=threading.Event()
def work(cancel):
    started.set(); cancel.wait(2)
with tasks.pool(workers=1,capacity=1) as p:
    job=p.submit(work); started.wait(1)
    try: p.submit(work)
    except RuntimeError as exc: print(exc)
    job.cancel(); job.result(2)
