import math
a=(3,4)
length=math.hypot(*a)
print(length,tuple(x/length for x in a))
