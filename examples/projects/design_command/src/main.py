class Add:
    def __init__(self,items,value): self.items,self.value=items,value
    def execute(self): self.items.append(self.value)
    def undo(self): self.items.pop()
items=[]; cmd=Add(items,42); cmd.execute(); print(items); cmd.undo(); print(items)
