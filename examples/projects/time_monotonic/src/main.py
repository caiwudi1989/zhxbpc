import time
start=time.perf_counter()
value=sum(range(10000))
print(value,"elapsed_nonnegative",time.perf_counter()-start>=0)
