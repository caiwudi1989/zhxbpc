from __future__ import annotations

import json
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths, atomic_write_json


def main():
    paths = Paths(root).ensure()
    cache = paths.build_cache / "ide"
    spec = cache / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    training_worker = cache / "training_worker.pyc"
    py_compile.compile(str(paths.src / "pcide/core/training_worker.py"), cfile=str(training_worker), dfile="training_worker.py", doraise=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(paths.src), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYINSTALLER_CONFIG_DIR=str(paths.cache / "pyinstaller"), PCIDE_ROOT=str(root))
    data = ((paths.src / "pcide/ui/editor.html", "pcide/ui"),
            (training_worker, "pcide/core"),
            (paths.src / "pcide/core/worker_js.cjs", "pcide/core"),
            (paths.src / "pcide/core/compile_js.cjs", "pcide/core"),
            (root / "third_party/bytenode", "third_party/bytenode"),
            (root / "docs/licenses", "licenses"),
            (root / "third_party/monaco", "third_party/monaco"),
            (paths.runtime / "node/node.exe", "runtime/node"),
            (root / "examples/plugins", "examples/plugins"),
            (paths.runtime / "modules", "runtime/modules"),
            (paths.runtime / "hosts/android", "runtime/hosts/android"),
            (root / "sdk/typescript/package/lib", "sdk/typescript/package/lib"),
            (paths.runtime / "prebuilt/project-runtime", "runtime/prebuilt/project-runtime"),
            (paths.runtime / "prebuilt/project-runtime-vision", "runtime/prebuilt/project-runtime-vision"),
            (paths.runtime / "prebuilt/project-runtime-node", "runtime/prebuilt/project-runtime-node"))
    command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
               "--name", "PCIDE", "--paths", str(paths.src), "--distpath", str(paths.build),
               "--workpath", str(cache / "work"), "--specpath", str(spec),
               "--hidden-import", "pcide.runtime_api", "--hidden-import", "PyInstaller.archive.readers",
               "--hidden-import", "PyInstaller.archive.writers", "--collect-data", "rapidocr_onnxruntime",
               "--exclude-module", "pip", "--exclude-module", "pytest", "--exclude-module", "torch", "--exclude-module", "ultralytics"]
    for source, destination in data:
        command.extend(["--add-data", f"{source};{destination}"])
    command.append(str(paths.src / "pcide/main.py"))
    subprocess.run(command, check=True, env=env, timeout=240)
    atomic_write_json(paths.build / "PCIDE/PCIDE.config.json", {"workspace": "../.."})
    print("IDE:", paths.build / "PCIDE/PCIDE.exe")


if __name__ == "__main__":
    main()
