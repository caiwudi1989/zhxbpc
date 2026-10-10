def add(a,b): return a+b
for a,b,expected in [(1,2,3),(-1,1,0),(0,0,0)]:
    assert add(a,b)==expected
print("3 regression cases passed")
