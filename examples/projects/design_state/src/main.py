class Machine:
    transitions={("idle","start"):"running",("running","stop"):"idle"}
    def __init__(self): self.state="idle"
    def send(self,event): self.state=self.transitions[(self.state,event)]
m=Machine(); m.send("start"); print(m.state); m.send("stop"); print(m.state)
