from contextlib import contextmanager
@contextmanager
def resource():
    print("open")
    try: yield "data"
    finally: print("close")
with resource() as value: print(value)
