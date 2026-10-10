from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths, atomic_write_json, sha256_file
from pcide.core.builder import STANDARD_LIBRARY_IMPORTS, runtime_fingerprint
from pcide.core.processes import run_bounded


def freeze(paths, profile):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(paths.src), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYINSTALLER_CONFIG_DIR=str(paths.cache / "pyinstaller"), PCIDE_ROOT=str(root))
    output = paths.runtime / "prebuilt"
    output.mkdir(exist_ok=True)
    stage = output / ("_freezing-" + uuid.uuid4().hex)
    cache = paths.build_cache / ("runtime-" + profile)
    spec = cache / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    directory = "project-runtime" if profile == "basic" else f"project-runtime-{profile}"
    target = output / directory
    backup = output / ("_previous-" + uuid.uuid4().hex)
    excludes = ["pip", "setuptools", "pytest", "torch", "ultralytics", "PySide6.QtWebEngineWidgets", "PyInstaller"]
    if profile in {"basic", "node"}:
        excludes += ["cv2", "numpy", "onnxruntime", "rapidocr_onnxruntime", "pcide.core.vision"]
    try:
        for mode, name, dist in (("onedir", "PCIDE.Runtime", stage), ("onefile", "PCIDE.Single", stage / "PCIDE.Runtime")):
            command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--" + mode,
                       "--name", name, "--hidden-import", "pcide.runtime_api", "--paths", str(paths.src),
                       "--distpath", str(dist), "--workpath", str(cache / mode), "--specpath", str(spec)]
            for module in excludes:
                command.extend(["--exclude-module", module])
            for module in STANDARD_LIBRARY_IMPORTS:
                command.extend(['--hidden-import', module])
            if profile == "vision":
                command.extend(["--collect-data", "rapidocr_onnxruntime"])
            if profile == "node":
                for source, destination in ((paths.runtime / "node/node.exe", "runtime/node"),
                    (paths.src / "pcide/core/worker_bytecode.cjs", "pcide/core"),
                    (paths.src / "pcide/core/source_contract.cjs", "pcide/core"),
                    (root / "third_party/bytenode/index.cjs", "pcide/core")):
                    if source.name == "index.cjs":
                        loader = cache / "bytenode.cjs"
                        shutil.copy2(source, loader)
                        source = loader
                    command.extend(["--add-data", f"{source};{destination}"])
            command.append(str(paths.src / "pcide/runtime/launcher.py"))
            run_bounded(command, cwd=root, environment=env, timeout=240, log_path=cache / ('freeze-' + mode + '.log'))
        material = stage / "PCIDE.Runtime"
        atomic_write_json(material / "runtime.json", {"fingerprint": runtime_fingerprint(paths, profile),
                          "python": sys.version, "cache_tag": sys.implementation.cache_tag, "profile": profile,
                          "files": {p.relative_to(material).as_posix(): sha256_file(p) for p in material.rglob("*") if p.is_file()}})
        if target.exists():
            target.rename(backup)
        material.rename(target)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if backup.exists() and not target.exists():
            backup.rename(target)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print("precompiled runtime:", target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["basic", "vision", "node", "all"], default="basic")
    args = parser.parse_args()
    paths = Paths(root).ensure()
    for profile in (["basic", "vision", "node"] if args.profile == "all" else [args.profile]):
        freeze(paths, profile)


if __name__ == "__main__":
    main()
