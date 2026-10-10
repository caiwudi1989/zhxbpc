from functools import lru_cache
@lru_cache(maxsize=8)
def square(value):
    return value*value
print(square(4),square(4),square.cache_info().hits)
square.cache_clear()
