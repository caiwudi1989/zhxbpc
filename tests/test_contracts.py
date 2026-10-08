from __future__ import annotations

import copy
import ast
import os
import shutil
import subprocess
import unittest
import uuid
import hashlib
import zipfile
from pathlib import Path

from pcide.core.data import DataError, generate_code, validate_data
from pcide.core.i18n import IdentifierMap, make_id
from pcide.core.paths import Paths
from pcide.core.project import Project, ProjectError, validate_form
from pcide.core.runtime_api import ui
from pcide.core.platform import validate_platform, discover_providers
from pcide.core.product import capability_summary, resolve_subsystems
from pcide.core.agent import AgentError, AgentSession, AgentTask, ToolSpec
from pcide.core.agent_client import AgentClient
from pcide.core.compiler import CompilerError, emit_python, parse
from pcide.core.database import Column, Table, generate_crud, generate_python_module, validate_schema
from pcide.core.api_center import ApiError, Endpoint, generate_client, generate_client_module, validate_endpoint
from pcide.core.ai_runtime import AiRuntimeError, ModelSpec, validate_model
from pcide.core.game_sdk import GameError, Scene, validate_scene
from pcide.core.agent_roles import role_catalog
from pcide.core.plugin_market import MarketError, install_archive, rollback_plugin, uninstall_plugin, upgrade_archive, validate_catalog
from pcide.core.unity import UnityError, bridge_manifest, generate_monobehaviour, inspect_project, scene_descriptor, write_generated_script


class ContractTests(unittest.TestCase):
    def setUp(self):
        # Normal mkdir preserves inherited ACLs for restricted child tokens.
        temp_root = Path(os.environ.get("PCIDE_TEST_TMP") or (Path(__file__).resolve().parents[1] / "cache" / "test-workspaces"))
        self.temp = temp_root / ("contract-extra-" + uuid.uuid4().hex)
        self.paths = Paths(self.temp).ensure()

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_data_scopes_api_contract_and_generation(self):
        model = validate_data({
            "variables": [{"name": "用户数", "type": "整数", "scope": "局部", "default": "3"}],
            "constants": [{"name": "版本", "value": "1"}],
            "apis": [{"name": "打开窗口", "library": "user32.dll", "return": "整数", "calling": "stdcall",
                      "permissions": ["ui.window"], "dependencies": ["user32"],
                      "params": [{"name": "句柄", "type": "整数"}]}],
        })
        self.assertEqual({item["scope"] for item in model["variables"]}, {"local"})
        self.assertEqual(model["apis"][0]["calling_convention"], "stdcall")
        self.assertEqual(len(model["apis"][0]["parameters"]), 1)
        for language in ("python", "javascript", "typescript"):
            source = generate_code(model, language)
            self.assertIn("打开窗口", source)
            self.assertIn(model["apis"][0]["id"], source)
        with self.assertRaises(DataError):
            validate_data({"variables": [{"id": "same", "label": "甲"}], "constants": [{"id": "same", "label": "乙"}]})

    def test_generation_literals_follow_declared_types(self):
        model = validate_data({
            "variables": [
                {"id": "text_value", "label": "文本", "type": "文本", "default": "1"},
                {"id": "count", "label": "数量", "type": "整数", "default": "7"},
                {"id": "enabled", "label": "启用", "type": "布尔", "default": "true"},
                {"id": "options", "label": "选项", "type": "对象", "default": '{"mode":"safe"}'},
            ],
            "constants": [{"id": "version", "label": "版本", "type": "文本", "value": "1"}],
        })
        python_source = generate_code(model, "python")
        ast.parse(python_source)
        self.assertIn('text_value: str = \'1\'', python_source)
        self.assertIn("count: int = 7", python_source)
        self.assertIn("enabled: bool = True", python_source)
        self.assertIn("options: dict = {'mode': 'safe'}", python_source)
        javascript_source = generate_code(model, "javascript")
        node = Paths().root / "runtime" / "node" / "node.exe"
        if node.is_file():
            script = self.temp / "generated.js"
            script.write_text(javascript_source, encoding="utf-8")
            result = subprocess.run([str(node), "--check", str(script)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        typescript_source = generate_code(model, "typescript")
        self.assertIn('let text_value: string = "1";', typescript_source)
        self.assertIn("let count: number = 7;", typescript_source)
        self.assertIn("let enabled: boolean = true;", typescript_source)

    def test_chinese_id_mapping_is_bidirectional(self):
        self.assertEqual(make_id("运行按钮", prefix="value", used=("value",)), "value_2")
        mapping = IdentifierMap([{"id": "Button1", "label": "运行按钮"}])
        self.assertEqual(mapping.to_id("运行按钮"), "Button1")
        self.assertEqual(mapping.to_label("Button1"), "运行按钮")
        with self.assertRaises(ValueError):
            mapping.add("Button1", "另一个名称")
        self.assertEqual(ui.open("settings.form.json"), {"kind": "ui.window.open", "window": "settings.form.json"})
        self.assertEqual(ui.close("settings.form.json"), {"kind": "ui.window.close", "window": "settings.form.json"})
        with self.assertRaises(ValueError):
            ui.open("")

    def test_independent_windows_and_layout_contract(self):
        project = Project.create(self.paths, "windows")
        secondary = copy.deepcopy(project.load_form())
        secondary["form"]["title"] = "设置窗口"
        secondary["form"]["window"].update({"fixed_width": 500, "fixed_height": 300, "anchor": "bottom_right", "dock": "none"})
        secondary["controls"][0]["properties"].update({"anchor": "bottom_right", "auto_fill": False})
        project.save_window("settings.form.json", secondary)
        self.assertEqual([path.name for path in project.window_paths()], ["main.form.json", "settings.form.json"])
        self.assertIn("ui/settings.form.json", {path.relative_to(project.root).as_posix() for path in project.input_files_for_build()})
        loaded = project.load_window("settings.form.json")
        self.assertEqual(loaded["form"]["window"]["fixed_width"], 500)
        with self.assertRaises(ProjectError):
            project.load_window("../outside.form.json")
        secondary["form"]["events"].update({"resize": "on_resize", "close": "on_close"})
        self.assertEqual(validate_form(secondary)["form"]["events"]["close"], "on_close")
        invalid = copy.deepcopy(secondary)
        invalid["form"]["window"]["fixed_width"] = 50
        with self.assertRaises(ProjectError):
            validate_form(invalid)
        invalid = copy.deepcopy(secondary)
        invalid["form"]["window"].update({"fixed_width": 900, "max_width": 800})
        with self.assertRaises(ProjectError):
            validate_form(invalid)

    def test_platform_capability_contract(self):
        platform = validate_platform({
            "version": 1,
            "capabilities": {"ai": {"enabled": True, "backends": ["onnx", "opencv"]}},
            "providers": [{"id": "acme.ai", "kind": "ai", "version": "1.0.0"}],
        })
        self.assertTrue(platform["capabilities"]["ai"]["enabled"])
        self.assertEqual(platform["providers"][0]["kind"], "ai")
        with self.assertRaises(ValueError):
            validate_platform({"version": 1, "providers": [{"id": "acme.ai", "kind": "ai"}, {"id": "acme.ai", "kind": "ai"}]})

    def test_provider_discovery_is_manifest_only(self):
        providers = self.temp / "providers" / "acme.ai"
        providers.mkdir(parents=True)
        (providers / "provider.json").write_text('{"id":"acme.ai","kind":"ai","version":"1.0.0"}', encoding="utf-8")
        (providers / "run.py").write_text('raise RuntimeError("must not execute")', encoding="utf-8")
        found = discover_providers(self.temp)
        self.assertEqual(found[0]["id"], "acme.ai")
        self.assertEqual(found[0]["manifest"], "providers/acme.ai/provider.json")
        project = Project.create(self.paths, "provider-project")
        target = project.root / "providers" / "acme.ai"
        target.mkdir(parents=True)
        (target / "provider.json").write_text('{"id":"acme.ai","kind":"ai","version":"1.0.0"}', encoding="utf-8")
        self.assertIn("providers/acme.ai/provider.json", {p.relative_to(project.root).as_posix() for p in project.input_files_for_build()})

    def test_product_subsystem_catalog(self):
        rows = resolve_subsystems({"version": 1, "capabilities": {"ai": {"enabled": True}}})
        self.assertEqual({row["kind"] for row in rows}, {"database", "api", "script", "ai", "game", "compiler", "agent", "runtime"})
        summary = capability_summary({"version": 1, "capabilities": {"ai": {"enabled": True}}})
        self.assertEqual(summary["total"], 8)
        self.assertGreaterEqual(summary["enabled"], 1)

    def test_agent_session_plan_tools_and_workspace_guard(self):
        project = Project.create(self.paths, "agent-project")
        source = project.root / "src" / "main.py"
        source.write_text("value = 1\n", encoding="utf-8")
        task = AgentTask("修改入口", str(project.root), frozenset({"src/main.py"}), allow_writes=True)
        session = AgentSession(task)
        session._tools = {
            "read": ToolSpec("read", "读取文件", lambda args: session.guard.read(args["path"])),
            "write": ToolSpec("write", "写入文件", lambda args: session.guard.write(args["path"], args["content"]), mutating=True),
        }
        result = session.run(lambda _task, _events: [
            {"tool": "read", "arguments": {"path": "src/main.py"}},
            {"tool": "write", "arguments": {"path": "src/main.py", "content": "value = 2\n"}},
        ])
        self.assertEqual(result.state.value, "completed")
        self.assertEqual(source.read_text(encoding="utf-8"), "value = 2\n")
        with self.assertRaises(AgentError):
            session.guard.write("../escape.py", "x = 1\n")
        class FakeClient:
            def __init__(self):
                self.calls = 0
            def complete(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    return type("Reply", (), {"content": "", "tool_calls": ({"id": "1", "function": {"name": "read", "arguments": '{"path":"src/main.py"}'}},)})()
                return type("Reply", (), {"content": "已检查入口文件", "tool_calls": ()})()
        inspect = AgentSession(AgentTask("检查入口", str(project.root)), [
            ToolSpec("read", "读取", lambda args: inspect.guard.read(args["path"]))
        ])
        checked = inspect.run_model(FakeClient())
        self.assertEqual(checked.state.value, "completed")
        self.assertEqual(checked.reply, "已检查入口文件")

    def test_agent_client_parses_structured_tool_calls(self):
        import unittest.mock as mock
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit):
                return b'{"choices":[{"message":{"content":"ok","tool_calls":[{"id":"c1","function":{"name":"read_file","arguments":"{}"}}]}}]}'
        with mock.patch("pcide.core.agent_client.urllib.request.urlopen", return_value=Response()):
            reply = AgentClient("http://127.0.0.1:8000/v1", "secret", "model").complete([], [])
        self.assertEqual(reply.content, "ok")
        self.assertEqual(reply.tool_calls[0]["id"], "c1")

    def test_compiler_database_api_ai_game_and_roles_contracts(self):
        source = ".版本 2\n.程序集 窗口程序集1\n.子程序 按钮1_被单击\n信息框(\"你好\")\n"
        self.assertIn("def ", emit_python(parse(source)))
        with self.assertRaises(CompilerError):
            parse(".版本 1\n.子程序 主程序\n")
        schema = validate_schema({"version": 1, "tables": [{"name": "users", "columns": [{"name": "id", "type": "INTEGER", "primary_key": True}, {"name": "name"}]}]})
        self.assertIn("INSERT INTO users", generate_crud(Table("users", tuple(Column(**c) for c in schema["tables"][0]["columns"])))["create"])
        ast.parse(generate_python_module(schema))
        with self.assertRaises(Exception):
            validate_schema({"version": 1, "tables": [{"name": "users", "columns": [{"name": "id", "type": "INTEGER", "primary_key": "false"}]}]})
        self.assertIn("api_call", generate_client(Endpoint("api_call", "接口", "GET", "/v1/data")))
        self.assertIn("apiRequest", generate_client_module([Endpoint("api-call", "接口", "GET", "/v1/data")], "javascript"))
        with self.assertRaises(ApiError):
            validate_endpoint({"id": "bad", "name": "接口", "path": "/v1", "timeout_seconds": "nope"})
        model = self.temp / "model.onnx"; model.write_bytes(b"model")
        self.assertEqual(validate_model(ModelSpec("m", "model.onnx", "detection"), self.temp).id, "m")
        with self.assertRaises(GameError):
            validate_scene(Scene("scene", entities=[{}], camera={"position": [0, 1]}))
        self.assertGreaterEqual(len(role_catalog()), 6)
        with self.assertRaises(MarketError):
            validate_catalog({"version": 1, "plugins": [{"id": "x", "version": "1.0.0", "sha256": "bad"}]})

    def test_unity_bridge_contract(self):
        unity = self.temp / "UnityGame"
        for folder in ("Assets", "Packages", "ProjectSettings"):
            (unity / folder).mkdir(parents=True)
        (unity / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.1f1\n", encoding="utf-8")
        (unity / "Assets" / "Main.unity").write_text("%YAML 1.1\n", encoding="utf-8")
        project = inspect_project(unity)
        self.assertEqual(project.version, "6000.0.1f1")
        target = write_generated_script(project, "MainBridge")
        self.assertIn("MonoBehaviour", target.read_text(encoding="utf-8"))
        self.assertTrue(scene_descriptor(project, "Main")["exists"])
        self.assertEqual(bridge_manifest(project)["provider"], "unity")
        with self.assertRaises(UnityError):
            inspect_project(self.temp / "not-unity")

    def test_chinese_project_entry_is_supported(self):
        project = Project.create(self.paths, "zhxb-project", "zhxb")
        self.assertEqual(project.entry_path.suffix, ".zhxb")
        self.assertEqual(project.manifest["language"], "zhxb")
        self.assertIn(".版本 2", project.entry_path.read_text(encoding="utf-8"))

    def test_project_copy_rejects_symlinks_and_roundtrips(self):
        source = Project.create(self.paths, "copy-source")
        (source.root / "resources" / "readme.txt").write_text("ok", encoding="utf-8")
        destination = self.paths.project("copy-target")
        copied = Project.copy_to(source.root, destination)
        self.assertEqual(copied.manifest["name"], "copy-source")
        self.assertEqual((destination / "resources" / "readme.txt").read_text(encoding="utf-8"), "ok")
        bad = self.paths.project("copy-bad")
        bad.mkdir(parents=True)
        (bad / ".pcide").mkdir()
        (bad / ".pcide" / "project.json").write_text((source.ide_dir / "project.json").read_text(encoding="utf-8"), encoding="utf-8")
        link = bad / "escape.txt"
        try:
            link.symlink_to(source.entry_path)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        with self.assertRaises(ProjectError):
            Project.copy_to(bad, self.paths.project("copy-link-target"))

    def test_plugin_market_upgrade_and_rollback(self):
        root = self.temp / "plugins"
        archive = self.temp / "demo.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("plugin.json", '{"id":"demo.plugin","version":"1.0.0"}')
        item = {"id": "demo.plugin", "version": "1.0.0", "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
        install_archive(item, archive, root)
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("plugin.json", '{"id":"demo.plugin","version":"2.0.0"}')
        item["version"] = "2.0.0"
        item["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        upgrade_archive(item, archive, root)
        self.assertIn("2.0.0", (root / "demo.plugin" / "plugin.json").read_text(encoding="utf-8"))
        rollback_plugin("demo.plugin", root)
        self.assertIn("1.0.0", (root / "demo.plugin" / "plugin.json").read_text(encoding="utf-8"))
        with self.assertRaises(MarketError):
            install_archive(item, archive, root)
        uninstall_plugin("demo.plugin", root)
        self.assertFalse((root / "demo.plugin").exists())
        with self.assertRaises(MarketError):
            uninstall_plugin("demo.plugin", root)


if __name__ == "__main__":
    unittest.main()
