from pcide.runtime_api import tasks
from concurrent.futures import TimeoutError
import threading
started=threading.Event()
def work(cancel): started.set(); cancel.wait(2); return "stopped"
with tasks.pool(workers=1,capacity=2) as p:
    job=p.submit(work); started.wait(1)
    try: job.result(0.01)
    except TimeoutError: print("timeout"); job.cancel()
    print(job.result(2))
