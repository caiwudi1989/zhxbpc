from pcide.runtime_api import tasks
with tasks.pool(workers=2,capacity=4) as p:
    jobs=[p.submit(lambda cancel,n:n*n,n) for n in range(4)]
    print([j.result(5) for j in jobs])
