class Repository:
    def __init__(self): self.data={}
    def put(self,key,value): self.data[key]=value
    def get(self,key): return self.data[key]
r=Repository(); r.put("name","PCIDE"); print(r.get("name"))
