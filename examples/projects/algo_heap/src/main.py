import heapq
q=[]
for priority,name in [(3,"low"),(1,"high"),(2,"normal")]:
    heapq.heappush(q,(priority,name))
while q:
    print(heapq.heappop(q)[1])
