from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.project import Project
from pcide.core.builder import BuildManager


def main():
    paths = Paths(root).ensure()
    manager = BuildManager(paths)
    evidence = []
    for name in ("HelloAutomation", "JavaScriptDemo", "TypeScriptDemo"):
        project = Project.open(paths.project(name))
        start = time.perf_counter()
        result = manager.build(project, "standalone")
        result["build_seconds"] = round(time.perf_counter()-start, 3)
        start = time.perf_counter()
        cached = manager.build(project, "standalone")
        result["cached_seconds"] = round(time.perf_counter()-start, 3)
        result["cached"] = cached["cache_hit"]
        env = os.environ.copy()
        env.update(PCIDE_PYTHON=str(paths.cache / "absent-python.exe"), PYTHONPATH="", PCIDE_DATA_ROOT=str(paths.cache / "delivery-runtime" / name))
        report = paths.logs / (name + "-exe-report.json")
        with (paths.logs / (name + "-exe.log")).open("w", encoding="utf-8") as log:
            completed = subprocess.run([result["artifact"], "--verify", "--report", str(report)], env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        result["exit_code"] = completed.returncode
        evidence.append(result)
        if completed.returncode:
            atomic_write_json(paths.logs / "delivery.json", evidence)
            raise RuntimeError(f"customer EXE verification failed: {name} {completed.returncode}")
    atomic_write_json(paths.logs / "delivery.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
