from collections import deque
graph={"A":["B","C"],"B":["D"],"C":[],"D":[]}
q=deque(["A"]); seen={"A"}; result=[]
while q:
    node=q.popleft(); result.append(node)
    for child in graph[node]:
        if child not in seen:
            seen.add(child); q.append(child)
print(result)
