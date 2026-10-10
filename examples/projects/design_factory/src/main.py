class Factory:
    def __init__(self): self.builders={}
    def register(self,key,builder):
        if key in self.builders: raise ValueError("重复类型")
        self.builders[key]=builder
    def create(self,key,**config): return self.builders[key](**config)
f=Factory()
f.register("label",lambda text:{"type":"Label","text":text})
print(f.create("label",text="ready"))
