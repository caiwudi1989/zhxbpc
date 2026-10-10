"""Transactionally promote the reviewed development staging IDE."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
build = (root / 'build').resolve()
staging = (build / 'development-staging-20261010' / 'PCIDE').resolve()
target = (build / 'PCIDE').resolve()
backup = (build / 'development-previous-20261010').resolve()

for path in (build, staging, target, backup):
    if not path.is_relative_to(build):
        raise RuntimeError('promotion path escaped build directory')
if not (staging / 'PCIDE.exe').is_file() or not (staging / '_internal').is_dir():
    raise RuntimeError('staging IDE is incomplete')
if target.exists():
    try:
        with (target / 'PCIDE.exe').open('r+b') as handle:
            handle.seek(0)
    except OSError as exc:
        raise RuntimeError('existing build/PCIDE is running or not writable') from exc
if backup.exists():
    raise RuntimeError(f'rollback directory already exists: {backup}')

old_moved = False
new_moved = False
try:
    if target.exists():
        target.rename(backup)
        old_moved = True
    staging.rename(target)
    new_moved = True
    config = target / 'PCIDE.config.json'
    config.write_text(json.dumps({'workspace': os.path.relpath(root, target)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not config.read_text(encoding='utf-8').strip():
        raise RuntimeError('promoted config is empty')
    print('promoted:', target)
    print('rollback:', backup if old_moved else 'none')
except Exception:
    if new_moved and target.exists():
        target.rename(staging)
    if old_moved and backup.exists():
        backup.rename(target)
    raise
