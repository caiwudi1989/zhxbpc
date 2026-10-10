class Events:
    def __init__(self): self.listeners=[]
    def subscribe(self,fn): self.listeners.append(fn)
    def emit(self,value):
        for fn in tuple(self.listeners): fn(value)
    def unsubscribe(self,fn): self.listeners.remove(fn)
e=Events(); e.subscribe(print); e.emit("once"); e.unsubscribe(print); e.emit("silent")
