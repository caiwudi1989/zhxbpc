from pathlib import Path
def safe_path(name):
    base=Path("resources").resolve()
    target=(base/name).resolve()
    if not target.is_relative_to(base):
        raise ValueError("路径越界")
    return target.name
print(safe_path("data.txt"))
try:
    safe_path("../../escape")
except ValueError as exc:
    print(exc)
