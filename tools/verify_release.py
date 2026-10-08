from __future__ import annotations

import json
import ctypes
import msvcrt
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from pcide.core.builder import FORBIDDEN_PARTS, FORBIDDEN_SOURCE
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.processes import ProcessJob
from pcide.core.project import Project
from pcide.core.plugins import write_example_plugins


def prepare_probes(workspace, paths):
    probe_paths = Paths(workspace).ensure()
    vision = Project.create(probe_paths, "VisionSmoke")
    vision.manifest["modules"] = ["vision"]
    vision.save_manifest()
    from PIL import Image, ImageDraw, ImageFont
    with Image.new("RGB", (500, 100), "white") as image:
        ImageDraw.Draw(image).text((15, 15), "PCIDE 2026", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40))
        image.save(vision.root / "resources/ocr.png")
    visual = json.loads((paths.logs / "vision-verification.json").read_text(encoding="utf-8"))
    shutil.copy2(visual["onnx"], vision.root / "resources/test.onnx")
    vision.entry_path.write_text(vision.entry_path.read_text(encoding="utf-8") +
        "\nfrom pcide.runtime_api import ocr, yolo\n"
        "ocr_result = ocr('resources/ocr.png')\n"
        "ocr_text = ' '.join(item['text'] for item in ocr_result['items'])\n"
        "assert 'PCIDE' in ocr_text and '2026' in ocr_text, ocr_result\n"
        "assert yolo('resources/ocr.png', 'resources/test.onnx')['shape'] == [1, 5, 8400]\n"
        "print('real OCR and ONNX passed')\n", encoding="utf-8")
    plugin = Project.create(probe_paths, "PluginSmoke")
    write_example_plugins(plugin.root)
    plugin.manifest["permissions"] = ["vision.simulated", "native.example"]
    plugin.save_manifest()
    plugin.entry_path.write_text(plugin.entry_path.read_text(encoding="utf-8") +
        "\nfrom pathlib import Path\nfrom pcide.core.plugins import PluginRegistry\n"
        "registry = PluginRegistry(Path.cwd(), ['vision.simulated', 'native.example'])\n"
        "try:\n    for plugin in registry.discover():\n        print(registry.call(plugin.id, plugin.capabilities[0]))\n"
        "finally:\n    registry.close()\n", encoding="utf-8")


def run_owned(command, environment, cwd, log_path, timeout):
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        job = None
        try:
            job = ProcessJob(process)
            code = process.wait(timeout=timeout)
        finally:
            if job:
                job.close()
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    if code:
        raise RuntimeError(f"verification exited {code}: {log_path}")
    return round(time.perf_counter() - started, 3)


def check_archive(artifact, language):
    from PyInstaller.archive.readers import CArchiveReader
    members = list(CArchiveReader(str(artifact)).toc)
    payload = [name.replace("\\", "/") for name in members if name.replace("\\", "/").startswith("payload/")]
    suffix = ".pyc" if language == "python" else ".jsc"
    if "payload/src/main" + suffix not in payload:
        raise RuntimeError("compiled project entry is missing")
    for name in members:
        path = Path(name.replace("\\", "/"))
        if "payload" not in path.parts:
            continue
        reviewed_host = path.suffix == ".cjs" and "payload" not in path.parts
        if any(part in FORBIDDEN_PARTS for part in path.parts) or path.suffix.lower() in FORBIDDEN_SOURCE and not reviewed_host:
            raise RuntimeError(f"development/source asset in customer EXE: {name}")
    return payload


def verify_worker_lifecycle(executable, workspace, environment, paths):
    project = Project.create(Paths(workspace).ensure(), "WorkerLifecycle")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                                    ctypes.POINTER(wintypes.DWORD)]
    kernel.PeekNamedPipe.restype = wintypes.BOOL
    results = []
    for case in ("native_event", "cancel", "disconnect", "invalid", "timeout", "crash"):
        source = ("import os\nos._exit(23)\n" if case == "crash" else
                  "from pcide.runtime_api import ui\n"
                  "def native_event(payload):\n"
                  "    import numpy\n"
                  "    ui.set('Label1', text=str(numpy.int64(42)))\n")
        project.entry_path.write_text(source, encoding="utf-8")
        session = uuid.uuid4().hex
        pending, records = bytearray(), []
        alive_before_termination = None
        with (paths.logs / ("frozen-worker-" + case + ".log")).open("wb") as log:
            process = subprocess.Popen([str(executable), "--worker"], cwd=project.root, env=environment,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            job = None
            try:
                job = ProcessJob(process)
                handle = msvcrt.get_osfhandle(process.stdout.fileno())
                def send(command):
                    process.stdin.write((json.dumps(command) + "\n").encode("utf-8"))
                    process.stdin.flush()
                def expect(kind, request_id=None):
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        while b"\n" in pending:
                            line, _, rest = pending.partition(b"\n")
                            pending[:] = rest
                            record = json.loads(line)
                            if record["session"] != session:
                                raise RuntimeError("frozen worker replied to the wrong session")
                            records.append(record)
                            if record["kind"] == kind and (request_id is None or record.get("request_id") == request_id):
                                return record
                        available = wintypes.DWORD()
                        if not kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                            raise RuntimeError(f"frozen worker disconnected before {kind}")
                        if available.value:
                            pending.extend(os.read(process.stdout.fileno(), min(available.value, 65536)))
                            if len(pending) > 65536 or len(records) > 100:
                                raise RuntimeError("frozen worker output exceeded probe limit")
                        else:
                            time.sleep(.05)
                    raise TimeoutError(f"frozen worker did not produce {kind}")
                send({"project": str(project.root), "session": session, "keep_alive": True})
                if case == "crash":
                    expected = 23
                else:
                    expect("ready")
                    if case == "native_event":
                        send({"session": session, "command": "event", "handler": "missing", "request_id": "failed"})
                        expect("error", "failed")
                        command = json.dumps({"session": session, "command": "event", "handler": "native_event", "request_id": "native"})
                        process.stdin.write(command[:20].encode())
                        process.stdin.flush()
                        time.sleep(.1)
                        process.stdin.write((command[20:] + "\n").encode())
                        process.stdin.flush()
                        expect("ui.set")
                        expect("event.done", "native")
                        if not any(record.get("properties", {}).get("text") == "42" for record in records):
                            raise RuntimeError("frozen event did not import/use NumPy")
                        send({"session": session, "command": "stop"})
                        expected = 130
                    elif case == "cancel":
                        send({"session": session, "command": "stop"})
                        expected = 130
                    elif case == "disconnect":
                        process.stdin.close()
                        expected = 130
                    elif case == "invalid":
                        process.stdin.write(b"{\n")
                        process.stdin.flush()
                        expect("error")
                        expected = 1
                    else:
                        process.stdin.write(b'{"partial":')
                        process.stdin.flush()
                        alive_before_termination = process.poll() is None
                        if not alive_before_termination:
                            raise RuntimeError("partial command worker exited before forced timeout termination")
                        try:
                            process.wait(timeout=.2)
                            raise RuntimeError("partial command unexpectedly completed")
                        except subprocess.TimeoutExpired:
                            job.close()
                        expected = None
                code = process.wait(timeout=5)
                if expected is not None and code != expected:
                    raise RuntimeError(f"frozen worker {case} exited {code}, expected {expected}")
                results.append({"case": case, "exit_code": code, "ok": True, "pid": process.pid,
                                "alive_before_termination": alive_before_termination})
            finally:
                if job:
                    job.close()
                elif process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                process.stdin.close()
                process.stdout.close()
            results[-1]["reaped"] = process.poll() is not None and job.closed
    return results


def main():
    paths = Paths(root).ensure()
    executable = paths.build / "PCIDE/PCIDE.exe"
    if not executable.is_file():
        raise RuntimeError("freeze the IDE before release verification")
    scratch = Path(tempfile.mkdtemp(prefix="frozen-release-", dir=paths.cache))
    evidence = {"ok": False, "date_utc": datetime.now(timezone.utc).isoformat(), "ide": str(executable),
                "boundary": "Local Windows; isolated workspace with no development Python, SDK or source tree", "projects": []}
    report_path = paths.logs / "frozen-release.json"
    environment = os.environ.copy()
    environment.update(PCIDE_ROOT=str(scratch), PCIDE_PYTHON=str(scratch / "absent-python.exe"), PYTHONPATH="",
                       PYTHONDONTWRITEBYTECODE="1", PCIDE_DATA_ROOT=str(scratch / "customer-data"))
    environment.pop("PCIDE_NODE", None)
    try:
        prepare_probes(scratch, paths)
        for name in ("HelloAutomation", "JavaScriptDemo", "TypeScriptDemo", "VisionSmoke", "PluginSmoke"):
            project = scratch / "projects" / name
            if not project.is_dir():
                shutil.copytree(paths.project(name), project)
            smoke_report = paths.logs / (name + "-frozen-ide.json")
            seconds = run_owned([str(executable), "--smoke", "--build", "--project", str(project), "--report", str(smoke_report)],
                                environment, scratch, paths.logs / (name + "-frozen-ide.log"), 90)
            smoke = json.loads(smoke_report.read_text(encoding="utf-8"))
            if not smoke["frozen"] or smoke["script_exit"] or not smoke["monaco_assets"] or not smoke["ui_updates"]:
                raise RuntimeError(f"frozen script/event gate failed: {smoke_report}")
            if Path(smoke["resources"]) != executable.parent / "_internal":
                raise RuntimeError("IDE did not use its bundled resource directory")
            if smoke["build"]["cache_hit"]:
                raise RuntimeError("fresh frozen build unexpectedly used a completed artifact")
            artifact = Path(smoke["build"]["artifact"])
            payload = check_archive(artifact, smoke["language"])
            portable_folder = scratch / "portable" / name
            portable_folder.mkdir(parents=True)
            portable = portable_folder / artifact.name
            shutil.copy2(artifact, portable)
            customer_report = paths.logs / (name + "-frozen-customer.json")
            customer_seconds = run_owned([str(portable), "--verify", "--report", str(customer_report)], environment,
                                         portable_folder, paths.logs / (name + "-frozen-customer.log"), 90)
            customer = json.loads(customer_report.read_text(encoding="utf-8"))
            if customer["exit_code"] or not customer["frozen"] or not any(m["kind"] == "ui.set" for m in customer["messages"]):
                raise RuntimeError(f"portable customer event gate failed: {customer_report}")
            if name == "VisionSmoke" and "real OCR and ONNX passed" not in customer["output"]:
                raise RuntimeError("real customer vision did not execute")
            if name == "PluginSmoke" and not all(value in customer["output"] for value in ("dotnet", "42", "simulated")):
                raise RuntimeError("customer extension hosts did not execute")
            if list(portable_folder.iterdir()) != [portable]:
                raise RuntimeError("customer execution created external runtime/source files")
            evidence["projects"].append({"name": name, "language": smoke["language"], "ide_seconds": seconds,
                                         "customer_seconds": customer_seconds, "payload": payload, "exit_code": 0})
            atomic_write_json(report_path, evidence)
        ui_report = paths.logs / "frozen-ui-smoke.json"
        evidence["ui_seconds"] = run_owned([str(executable), "--ui-smoke", "--project", str(scratch / "projects/TypeScriptDemo"),
                                            "--report", str(ui_report), "--screenshot", str(paths.logs / "frozen-ide.png")],
                                           environment, scratch, paths.logs / "frozen-ui-smoke.log", 30)
        ui = json.loads(ui_report.read_text(encoding="utf-8"))
        # WebEngine/Monaco is preferred, but the frozen IDE must be able to
        # complete UI smoke with the bounded native editor fallback on
        # restricted Windows hosts where Chromium/Mojo cannot initialize.
        editor_backend = ui.get("editor")
        if (not ui.get("qt") or not ui.get("editor_ready") or not ui.get("frozen")
                or editor_backend not in {"monaco", "native"}):
            raise RuntimeError(f"frozen editor gate failed ({editor_backend!r}): {ui_report}")
        evidence["ui_editor"] = editor_backend
        evidence["ui_monaco"] = bool(ui.get("monaco"))
        evidence["worker_lifecycle"] = verify_worker_lifecycle(
            executable.parent / "_internal/runtime/prebuilt/project-runtime-vision/PCIDE.Runtime.exe", scratch, environment, paths)
        evidence["ok"] = True
    except Exception as exc:
        evidence["error"] = str(exc)
        raise
    finally:
        if scratch.parent != paths.cache:
            raise RuntimeError("verification cleanup boundary changed")
        shutil.rmtree(scratch)
        evidence["temporary_workspace_removed"] = True
        atomic_write_json(report_path, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
