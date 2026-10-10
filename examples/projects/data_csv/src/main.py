import csv,io
s=io.StringIO()
w=csv.writer(s)
w.writerows([["name","score"],["Alice",95]])
print(list(csv.DictReader(io.StringIO(s.getvalue()))))
