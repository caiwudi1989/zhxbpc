import weakref,gc
class Item: pass
cache=weakref.WeakValueDictionary()
item=Item(); cache["id"]=item
print(len(cache)); del item; gc.collect(); print(len(cache))
