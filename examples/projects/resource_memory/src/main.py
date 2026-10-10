import tracemalloc
tracemalloc.start()
data=bytearray(100000)
print("allocated",tracemalloc.get_traced_memory()[0]>90000)
del data
print("released",tracemalloc.get_traced_memory()[0]<90000)
tracemalloc.stop()
