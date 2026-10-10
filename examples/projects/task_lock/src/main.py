from pcide.runtime_api import tasks
import threading
lock=threading.Lock(); values=[]
def work(cancel,n):
    with lock: values.append(n)
with tasks.pool(workers=2,capacity=4) as p:
    jobs=[p.submit(work,n) for n in range(4)]
    for job in jobs: job.result(2)
print(sorted(values))
