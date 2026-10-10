from pcide.runtime_api import tasks
def work(cancel): raise ValueError("task failed")
with tasks.pool(workers=1,capacity=2) as p:
    job=p.submit(work)
    try: job.result(2)
    except ValueError as exc: print(exc)
