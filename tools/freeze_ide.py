from __future__ import annotations

import json
import argparse
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.processes import run_bounded
from pcide.core.builder import STANDARD_LIBRARY_IMPORTS


def main():
    paths = Paths(root).ensure()
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-directory', type=Path, default=paths.build)
    args = parser.parse_args()
    output = args.output_directory.resolve()
    if not output.is_relative_to(paths.build.resolve()):
        parser.error('IDE output directory must stay under build')
    output.mkdir(parents=True, exist_ok=True)
    current_exe = output / 'PCIDE/PCIDE.exe'
    if current_exe.is_file():
        try:
            # Windows denies write access to a running executable. Probe it
            # before PyInstaller starts cleaning sibling runtime assets.
            with current_exe.open('r+b'):
                pass
        except OSError as exc:
            raise RuntimeError('IDE 交付正在使用或不可写；请保存并关闭窗口，或指定独立 --output-directory') from exc
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
            (paths.src / "pcide/core/source_contract.cjs", "pcide/core"),
            (root / "third_party/bytenode", "third_party/bytenode"),
            (root / "docs/licenses", "licenses"),
            (root / "third_party/monaco", "third_party/monaco"),
            (paths.runtime / "node/node.exe", "runtime/node"),
            (root / "examples/plugins", "examples/plugins"),
            (root / 'examples/catalog.json', 'examples'),
            (root / 'examples/projects', 'examples/projects'),
            (root / 'docs/规范/development.md', 'docs'),
            (root / 'docs/规范/libraries.md', 'docs'),
            (root / 'docs/规范/pages.md', 'docs'),
            (paths.runtime / "modules", "runtime/modules"),
            (paths.runtime / "hosts/android", "runtime/hosts/android"),
            (root / "sdk/typescript/package/lib", "sdk/typescript/package/lib"),
            (paths.runtime / "prebuilt/project-runtime", "runtime/prebuilt/project-runtime"),
            (paths.runtime / "prebuilt/project-runtime-vision", "runtime/prebuilt/project-runtime-vision"),
            (paths.runtime / "prebuilt/project-runtime-node", "runtime/prebuilt/project-runtime-node"))
    command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
               "--name", "PCIDE", "--paths", str(paths.src), "--distpath", str(output),
               "--workpath", str(cache / "work"), "--specpath", str(spec),
               "--hidden-import", "pcide.runtime_api", "--hidden-import", "PyInstaller.archive.readers",
               "--hidden-import", "PyInstaller.archive.writers", "--collect-data", "rapidocr_onnxruntime",
               "--exclude-module", "pip", "--exclude-module", "pytest", "--exclude-module", "torch", "--exclude-module", "ultralytics"]
    for source, destination in data:
        command.extend(["--add-data", f"{source};{destination}"])
    for name in STANDARD_LIBRARY_IMPORTS:
        command.extend(['--hidden-import', name])
    command.append(str(paths.src / "pcide/main.py"))
    run_bounded(command, cwd=root, environment=env, timeout=240, log_path=cache / 'freeze.log')
    atomic_write_json(output / "PCIDE/PCIDE.config.json", {"workspace": os.path.relpath(root, output / 'PCIDE')})
    print("IDE:", output / "PCIDE/PCIDE.exe")


if __name__ == "__main__":
    main()
