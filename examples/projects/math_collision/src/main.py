def overlap(a,b):
    return a[0]<b[0]+b[2] and a[0]+a[2]>b[0] and a[1]<b[1]+b[3] and a[1]+a[3]>b[1]
print(overlap((0,0,10,10),(5,5,10,10)),overlap((0,0,10,10),(20,20,2,2)))
