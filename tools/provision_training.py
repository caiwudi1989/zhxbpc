from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-python", required=True)
    args = parser.parse_args()
    target = root / "runtime" / "training"
    subprocess.run([sys.executable, "-B", "-m", "venv", str(target)], check=True)
    # Copy only the transitive dependency closure of the two requested runtime
    # distributions. Source environment is queried read-only and never modified.
    script = """
import importlib.metadata as md, json
from packaging.requirements import Requirement
pending=['ultralytics','torch']; seen=set(); output=[]
while pending:
 name=pending.pop(); distribution=md.distribution(name); key=distribution.metadata['Name'].lower().replace('_','-')
 if key in seen: continue
 seen.add(key)
 files=[str(p) for p in distribution.files or [] if '..' not in p.parts and '__pycache__' not in p.parts]
 output.append({'name':key,'version':distribution.version,'root':str(distribution.locate_file('')),'files':files})
 for raw in distribution.requires or []:
  requirement=Requirement(raw)
  if not requirement.marker or requirement.marker.evaluate({'extra':''}):pending.append(requirement.name)
print(json.dumps(output))
"""
    completed = subprocess.run([args.source_python, "-B", "-c", script], check=True, capture_output=True, text=True, encoding="utf-8", timeout=30)
    packages = json.loads(completed.stdout)
    site = target / "Lib" / "site-packages"
    count, total = 0, 0
    for package in packages:
        source_root = Path(package["root"]).resolve()
        for name in package["files"]:
            source = (source_root / name).resolve()
            destination = (site / name).resolve()
            if not source.is_relative_to(source_root) or not destination.is_relative_to(site.resolve()):
                raise ValueError("runtime distribution path escaped boundary")
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                count += 1
                total += source.stat().st_size
    (target / "provenance.json").write_text(json.dumps([{k: v for k, v in p.items() if k != "files"} for p in packages], indent=2), encoding="utf-8")
    print(json.dumps({"distributions": len(packages), "files": count, "bytes": total, "target": str(target)}))


if __name__ == "__main__":
    main()
