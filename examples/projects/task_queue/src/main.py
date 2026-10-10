from pcide.runtime_api import tasks
import queue
q=queue.Queue(maxsize=4)
def produce(cancel):
    for n in range(3): q.put(n,timeout=1)
    q.put(None,timeout=1)
def consume(cancel):
    values=[]
    while not cancel.is_set():
        item=q.get(timeout=1)
        if item is None: return values
        values.append(item)
with tasks.pool(workers=2,capacity=4) as p:
    producer=p.submit(produce); consumer=p.submit(consume)
    producer.result(2); print(consumer.result(2))
