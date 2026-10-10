def validate(value):
    if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=100:
        raise ValueError("范围应为0..100")
    return value
print(validate(42))
try:
    validate(101)
except ValueError as exc:
    print(exc)
