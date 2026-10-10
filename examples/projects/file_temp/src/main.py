from contextlib import contextmanager
from pathlib import Path
import shutil, uuid

@contextmanager
def temporary_directory():
    root = Path("resources").resolve()
    directory = root / ("temp-" + uuid.uuid4().hex)
    directory.mkdir()  # Inherit the workspace permissions on Windows.
    try:
        yield directory
    finally:
        if directory.resolve().is_relative_to(root):
            shutil.rmtree(directory)

with temporary_directory() as directory:
    file = directory / "demo.txt"
    file.write_text("temporary", encoding="utf-8")
    print(file.read_text(encoding="utf-8"))
print("reclaimed", not directory.exists())
