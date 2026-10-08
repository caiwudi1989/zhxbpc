from pathlib import Path
from .paths import read_json, sha256_file


def verify_package(root, manifest_name="build.json", scope=None):
    root = Path(root).resolve()
    try:
        files = read_json(root / manifest_name, {}).get("files", {})
        if not isinstance(files, dict) or not files:
            return False
        directory = root / scope if scope else root
        actual = {p.relative_to(root).as_posix() for p in directory.rglob("*") if p.is_file() and p.relative_to(root).as_posix() != manifest_name}
        if actual != set(files):
            return False
        for name, digest in files.items():
            path = (root / name).resolve()
            if not path.is_relative_to(directory) or path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
                return False
        return True
    except (OSError, ValueError, TypeError, AttributeError):
        return False
