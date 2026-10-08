from __future__ import annotations

import copy
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from pcide.core.flow import FlowRunner, validate_flow
from pcide.core.label_io import read_boxes, write_boxes, write_data_yaml
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.plugins import PluginError, PluginManifest, PluginRegistry, write_example_plugins
from pcide.core.project import Project, ProjectError, relative_file, validate_form
from pcide.core.runner import ScriptRunner
from pcide.core.vision import VisionWorkbench


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="contract-", dir=Paths().ensure().cache))
        self.paths = Paths(self.temp).ensure()
        self.owned = []

    def tearDown(self):
        for resource in reversed(self.owned):
            if isinstance(resource, ScriptRunner):
                resource.stop()
                resource.wait()
            else:
                resource.close()
        shutil.rmtree(self.temp)

    def project(self, name="test", language="python", source=None):
        project = Project.create(self.paths, name, language)
        if source is not None:
            project.entry_path.write_text(source, encoding="utf-8")
        return project


class ProjectTests(WorkspaceCase):
    def test_roundtrip_stable_identity(self):
        project = self.project()
        control = project.add_control("Button", x=20, y=30)
        form = project.load_form()
        added = next(c for c in form["controls"] if c["id"] == control.id)
        self.assertEqual(added["x"], 20)
        added["name"] = "Renamed"
        project.save_form(form)
        self.assertEqual(Project.open(project.root).load_form()["controls"][-1]["id"], control.id)

    def test_malformed_form_and_path(self):
        form = self.project().load_form()
        for change in (lambda f: f["controls"].append(copy.deepcopy(f["controls"][0])),
                       lambda f: f["controls"][0].update(parent="Button1"),
                       lambda f: f["controls"][0].update(width=-1),
                       lambda f: f["controls"][0].update(events={"click": "evil();"}),
                       lambda f: f.update(controls=None)):
            with self.subTest(change=change):
                candidate = copy.deepcopy(form)
                change(candidate)
                with self.assertRaises(ProjectError):
                    validate_form(candidate)
        for value in ("", "../secret", "F:/outside", "src/../../outside"):
            with self.assertRaises(ProjectError):
                relative_file(self.paths.root, value)

    def test_invalid_execution_config_and_missing_entry(self):
        project = self.project()
        for timeout in (0, -1, float("nan"), "abc"):
            manifest = copy.deepcopy(project.manifest)
            manifest["execution"]["timeout_seconds"] = timeout
            with self.assertRaises(ProjectError):
                Project(project.root, manifest)
        project.entry_path.unlink()
        with self.assertRaises(ProjectError):
            Project.open(project.root)

    def test_project_file_management_protects_required_paths(self):
        project = self.project()
        source = project.root / "src" / "helper.py"
        source.write_text("value = 1\n", encoding="utf-8")
        renamed = project.rename_path(source, "renamed.py")
        self.assertEqual(renamed.name, "renamed.py")
        self.assertTrue(renamed.is_file())
        project.delete_path(renamed)
        self.assertFalse(renamed.exists())
        folder = project.root / "resources" / "icons"
        folder.mkdir(parents=True)
        (folder / "icon.txt").write_text("x", encoding="utf-8")
        project.delete_path(folder)
        self.assertFalse(folder.exists())
        for protected in (project.root, project.form_path, project.flow_path,
                          project.entry_path, project.ide_dir / "project.json", project.root / "src"):
            with self.assertRaises(ProjectError):
                project.delete_path(protected)
        with self.assertRaises(ProjectError):
            project.rename_path(project.entry_path, "other.py")
        with self.assertRaises(ProjectError):
            project.rename_path(project.root / "resources", "../outside")
        (project.root / "icons").mkdir()
        with self.assertRaises(ProjectError):
            project.rename_path(project.root / "resources", "icons")


class RuntimeTests(WorkspaceCase):
    def runner(self):
        runner = ScriptRunner()
        self.owned.append(runner)
        return runner

    def test_languages_events_and_error(self):
        for language in ("python", "javascript", "typescript"):
            with self.subTest(language=language):
                project = self.project(language, language)
                runner = self.runner()
                code, output, state = runner.run_sync(project, timeout=8, events=["on_Button1_click"])
                self.assertEqual(code, 0, state.error)
                self.assertIn("脚本已就绪", output)
                self.assertTrue(any(m.get("kind") == "ui.set" and m["id"] == "Label1" for m in runner.messages))
                self.assertEqual(state.status, "completed")
                project.entry_path.write_text("raise ValueError('bad')" if language == "python" else "throw Error('bad');", encoding="utf-8")
                code, _, state = runner.run_sync(project, timeout=8)
                self.assertEqual(code, 1)
                self.assertIn("bad", state.error)

    def test_python_normal_run_and_events_without_debug_trace(self):
        project = self.project(source=(
            "import sys\n"
            "assert sys.gettrace() is None, 'startup unexpectedly traced'\n"
            "def on_Button1_click(payload):\n"
            "    assert sys.gettrace() is None, 'event unexpectedly traced'\n"
            "    print('event executed without trace')\n"
        ))
        code, output, state = self.runner().run_sync(project, timeout=5, events=["on_Button1_click"])
        self.assertEqual(code, 0, state.error)
        self.assertIn("event executed without trace", output)

    def test_native_import_in_event_and_debug(self):
        project = self.project(source=(
            "def native_event(payload):\n"
            "    import numpy\n"
            "    print('native value', numpy.int64(42))\n"
        ))
        runner = self.runner()
        ready, completed = threading.Event(), threading.Event()
        def receive(record):
            if record["kind"] == "ready":
                ready.set()
            elif record["kind"] == "event.done":
                completed.set()
        runner.start(project, keep_alive=True, timeout=8, on_message=receive)
        self.assertTrue(ready.wait(3), runner.state.error)
        runner.event("native_event")
        self.assertTrue(completed.wait(3), runner.state.error)
        self.assertIn("native value 42", "".join(runner.lines))
        runner.stop()
        runner.wait()
        self.assertIsNone(runner.process)
        project.entry_path.write_text("import numpy\nprint(numpy.int64(42))\n", encoding="utf-8")
        def resume(record):
            if record["kind"] == "paused":
                runner.send("continue")
        code, output, state = runner.run_sync(project, timeout=8, debug=True, on_message=resume)
        self.assertEqual(code, 0, state.error)
        self.assertIn("42", output)

    def test_keep_alive_event_error_ownership_and_recovery(self):
        for language in ("python", "javascript", "typescript"):
            with self.subTest(language=language):
                runner = self.runner()
                ready, failed, completed = threading.Event(), threading.Event(), threading.Event()
                errors, replies = [], []
                def receive(record):
                    if record["kind"] == "ready":
                        ready.set()
                    elif record["kind"] == "error":
                        errors.append(record)
                        failed.set()
                    elif record["kind"] == "event.done":
                        replies.append(record)
                        completed.set()
                runner.start(self.project(language, language), keep_alive=True, timeout=8, on_message=receive)
                self.assertTrue(ready.wait(3), runner.state.error)
                request = runner.event("missing_handler")
                self.assertTrue(failed.wait(3), runner.state.error)
                self.assertEqual(errors[-1]["request_id"], request)
                request = runner.event("on_Button1_click")
                self.assertTrue(completed.wait(3), runner.state.error)
                self.assertEqual(replies[-1]["request_id"], request)
                runner.stop()
                runner.wait()
                self.assertIsNone(runner.process)

    def test_python_pipe_partial_commands_invalid_and_disconnect(self):
        project = self.project()
        runner = self.runner()
        ready, completed = threading.Event(), threading.Event()
        def receive(record):
            if record["kind"] == "ready":
                ready.set()
            elif record["kind"] == "event.done":
                completed.set()
        runner.start(project, keep_alive=True, timeout=8, on_message=receive)
        self.assertTrue(ready.wait(3), runner.state.error)
        command = json.dumps({"session": runner.session, "command": "event", "handler": "on_Button1_click", "request_id": "split"})
        runner.process.stdin.write(command[:20])
        runner.process.stdin.flush()
        time.sleep(.1)
        self.assertFalse(completed.is_set())
        runner.process.stdin.write(command[20:] + "\n")
        runner.process.stdin.flush()
        self.assertTrue(completed.wait(3), runner.state.error)
        runner.process.stdin.close()
        runner.wait(5)
        self.assertEqual(runner.state.exit_code, 130)
        self.assertIsNone(runner.job)
        for index, value in enumerate(("{\n", "x" * 65537 + "\n")):
            ready.clear()
            runner.start(project, keep_alive=True, timeout=8, on_message=receive)
            self.assertTrue(ready.wait(3), runner.state.error)
            try:
                runner.process.stdin.write(value)
                runner.process.stdin.flush()
            except OSError:
                pass
            runner.wait(5)
            self.assertEqual(runner.state.exit_code, 1, runner.state.error)
            self.assertIn("Expecting" if index == 0 else "command limit", runner.state.error)
            self.assertIsNone(runner.process)
            self.assertIsNone(runner.job)
        ready.clear()
        runner.start(project, keep_alive=True, timeout=.7, on_message=receive)
        self.assertTrue(ready.wait(.5), runner.state.error)
        runner.process.stdin.write('{"partial":')
        runner.process.stdin.flush()
        runner.wait(3)
        self.assertEqual(runner.state.exit_code, 124)
        self.assertIsNone(runner.process)
        self.assertIsNone(runner.job)
        project.entry_path.write_text("import os\nos._exit(23)\n", encoding="utf-8")
        code, _, state = runner.run_sync(project, timeout=3)
        self.assertEqual(code, 23)
        self.assertIn("worker exited 23", state.error)
        self.assertIsNone(runner.process)
        self.assertIsNone(runner.job)

    def test_keep_alive_event_ids_restart_stop(self):
        for language in ("python", "javascript", "typescript"):
            with self.subTest(language=language):
                project = self.project(language, language)
                runner = self.runner()
                ready, completed = threading.Event(), threading.Event()
                ids = []
                def receive(record):
                    if record["kind"] == "ready":
                        ready.set()
                    if record["kind"] == "event.done":
                        ids.append(record["request_id"])
                        completed.set()
                runner.start(project, timeout=8, keep_alive=True, on_message=receive)
                self.assertTrue(ready.wait(5), runner.state.error)
                with self.assertRaises(RuntimeError):
                    runner.start(project)
                request_id = runner.event("on_Button1_click", {"value": "test"})
                self.assertTrue(completed.wait(3))
                self.assertEqual(ids, [request_id])
                runner.stop()
                runner.wait()
                self.assertEqual(runner.state.status, "stopped")
                self.assertIsNone(runner.process)
                session = runner.session
                self.assertEqual(runner.run_sync(project, timeout=5)[0], 0)
                self.assertNotEqual(session, runner.session)

    def test_debug_breakpoint_step_variables_stack(self):
        for language in ("python", "javascript", "typescript"):
            with self.subTest(language=language):
                source = "value = 41\nvalue += 1\nprint(value)\n" if language == "python" else "let value = 41;\nvalue += 1;\nconsole.log(value);\n"
                project = self.project(language, language, source)
                runner = self.runner()
                pauses = []
                def receive(record):
                    if record["kind"] == "paused":
                        pauses.append(record)
                        runner.send("next" if record["line"] == 2 else "continue")
                runner.start(project, timeout=8, debug=True, breakpoints={str(project.entry_path): [2]}, on_message=receive)
                runner.wait(14)
                self.assertEqual(runner.state.exit_code, 0, runner.state.error)
                stopped = next((p for p in pauses if p["line"] == 2), None)
                self.assertIsNotNone(stopped, pauses)
                self.assertIn("41", stopped["variables"].get("value", ""))
                self.assertTrue(stopped["stack"])
                self.assertTrue(any(p["line"] == 3 for p in pauses), pauses)

    def test_timeout_output_bound_and_cleanup(self):
        for language in ("python", "javascript"):
            source = "import time\ntime.sleep(10)\n" if language == "python" else "while(true){}"
            project = self.project(language, language, source)
            runner = self.runner()
            code, _, state = runner.run_sync(project, timeout=.3)
            self.assertEqual(code, 124, state.error)
            self.assertEqual(state.status, "timeout")
            self.assertIsNone(runner.job)
        project = self.project("output", source="for i in range(100): print(i)\n")
        project.manifest["execution"]["max_output_lines"] = 10
        code, _, state = self.runner().run_sync(project, timeout=5)
        self.assertNotEqual(code, 0)
        self.assertIn("output limit", state.error)
        project = self.project("stderr", "javascript", "process.stderr.write('x'.repeat(2*1024*1024));")
        code, _, state = self.runner().run_sync(project, timeout=5)
        self.assertNotEqual(code, 0)
        self.assertIn("stderr log limit", state.error)


class FlowTests(WorkspaceCase):
    def test_dependencies_invalid_empty_timeout_cancel(self):
        runner = FlowRunner()
        flow = self.project().load_flow()
        self.assertTrue(runner.run(flow).ok)
        self.assertTrue(runner.run({"nodes": [], "edges": []}).ok)
        invalid = copy.deepcopy(flow)
        invalid["edges"].append(["yolo", "start"])
        with self.assertRaises(ValueError):
            validate_flow(invalid)
        sleep = {"nodes": [{"id": "wait", "kind": "sleep", "config": {"seconds": 3}}]}
        self.assertIn("timeout", runner.run(sleep, timeout=.1).error)
        cancelled = []
        thread = threading.Thread(target=lambda: cancelled.append(runner.run(sleep)))
        thread.start()
        time.sleep(.1)
        self.assertIn("already active", runner.run(flow).error)
        runner.cancel()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(cancelled[0].cancelled)
        self.assertTrue(runner.run(flow).ok)


class PluginTests(WorkspaceCase):
    def registry(self, project, permissions=None):
        write_example_plugins(project.root)
        registry = PluginRegistry(project.root, permissions)
        self.owned.append(registry)
        return registry

    def test_real_python_c_dotnet_hosts(self):
        registry = self.registry(self.project())
        manifests = {m.kind: m for m in registry.discover()}
        self.assertEqual(set(manifests), {"python", "native", "dotnet"})
        for kind, manifest in manifests.items():
            with self.subTest(kind=kind):
                load = registry.load(manifest.id)
                pid = registry.sessions[manifest.id].process.pid
                self.assertTrue(load["ok"])
                self.assertTrue(registry.load(manifest.id)["duplicate"])
                self.assertEqual(registry.sessions[manifest.id].process.pid, pid)
                result = registry.call(manifest.id, manifest.capabilities[0])
                if kind == "python":
                    self.assertTrue(result["result"]["simulated"])
                else:
                    self.assertEqual(result["result"]["value"], 42)
                session = registry.sessions[manifest.id]
                registry.unload(manifest.id)
                self.assertTrue(session.closed)
                self.assertFalse(session.reader.is_alive())

    def test_permissions_timeout_crash_reload(self):
        registry = self.registry(self.project(), ["vision.simulated"])
        with self.assertRaisesRegex(PluginError, "permissions"):
            registry.load("example.native_math")
        registry.permissions.add("native.example")
        for params, error in (({"sleep": True}, "timeout"), ({"crash": True}, "disconnected")):
            with self.assertRaisesRegex(PluginError, error):
                registry.call("example.native_math", "math.answer", params, timeout=.2)
            self.assertTrue(registry.sessions["example.native_math"].closed)
            self.assertEqual(registry.call("example.native_math", "math.answer")["result"]["value"], 42)

    def test_manifest_dependency_path_and_capability(self):
        project = self.project()
        registry = self.registry(project)
        registry.discover()
        raw = registry.plugins["example.mock_vision"][0].to_dict()
        for field, value in (("id", "bad id"), ("version", "x"), ("kind", "bad"), ("capabilities", None)):
            with self.assertRaises(PluginError):
                PluginManifest.from_dict({**raw, field: value})
        with self.assertRaisesRegex(PluginError, "not declared"):
            registry.call(raw["id"], "missing")
        path = project.root / "plugins/mock_vision/plugin.json"
        atomic_write_json(path, {**raw, "entry": "../native_math/native_math.dll"})
        with self.assertRaisesRegex(PluginError, "directory|escapes"):
            registry.discover()
        atomic_write_json(path, {**raw, "dependencies": {"missing": "1.0.0"}})
        with self.assertRaisesRegex(PluginError, "dependency"):
            registry.discover()


class VisionTests(WorkspaceCase):
    def test_labels_dataset_model_boundaries(self):
        vision = VisionWorkbench(self.project().root, self.paths)
        boxes = [{"class_id": 0, "cx": .5, "cy": .5, "w": .2, "h": .3}]
        annotation = vision.add_annotation("screen.png", boxes)
        self.assertEqual(read_boxes(annotation), boxes)
        with self.assertRaises(ValueError):
            write_boxes(annotation, [{**boxes[0], "w": float("nan")}])
        self.assertEqual(read_boxes(annotation), boxes)
        self.assertTrue(write_data_yaml(vision.dataset).is_file())
        self.assertTrue(vision.models.is_relative_to(self.paths.runtime))
        self.assertTrue(vision.logs.is_relative_to(self.paths.cache))
        self.assertEqual(vision.model_manifest()["annotations"], 1)
        with self.assertRaises(ValueError):
            vision.import_model(annotation)


if __name__ == "__main__":
    unittest.main()

