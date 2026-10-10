from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from pcide.core.builder import BuildError, BuildManager
from pcide.core.paths import Paths
from tests.test_core import WorkspaceCase


class BuildTests(WorkspaceCase):
    def manager(self):
        paths = Paths().ensure()
        paths.artifacts = self.temp / "artifacts"
        paths.artifacts.mkdir(exist_ok=True)
        return BuildManager(paths)

    def run_artifact(self, artifact):
        report = self.temp / "exe-report.json"
        env = os.environ.copy()
        env.update(PCIDE_PYTHON=str(self.temp / "no-python.exe"), PYTHONPATH="", PCIDE_DATA_ROOT=str(self.temp / "execution-cache"))
        result = subprocess.run([str(artifact), "--verify", "--report", str(report)], capture_output=True,
                                text=True, encoding="utf-8", env=env, timeout=90, cwd=self.temp)
        self.assertEqual(result.returncode, 0, (result.stderr or "") + (result.stdout or ""))
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["frozen"])
        self.assertIn("脚本已就绪", data["output"])
        self.assertTrue(any(m["kind"] == "ui.set" for m in data["messages"]))
        return data

    def test_directory_run_cache_change_delete_tamper_failure(self):
        project = self.project()
        project.entry_path.write_text(project.entry_path.read_text(encoding="utf-8") + "\nprint('\\u4e2d\\u6587')\n", encoding="utf-8")
        project.root.joinpath("src/helper.py").write_text("value = 42\n", encoding="utf-8")
        manager = self.manager()
        first = manager.build(project, "directory")
        artifact = Path(first["artifact"])
        self.assertEqual(artifact.read_bytes()[:2], b"MZ")
        self.assertIn("\u4e2d\u6587", self.run_artifact(artifact)["output"])
        self.assertTrue(manager.build(project, "directory")["cache_hit"])
        project.root.joinpath("src/helper.py").write_text("value = 43\n", encoding="utf-8")
        changed = manager.build(project, "directory")
        self.assertEqual(changed["changed"], ["src/helper.py"])
        project.root.joinpath("src/helper.py").unlink()
        deleted = manager.build(project, "directory")
        self.assertEqual(deleted["removed"], ["src/helper.py"])
        self.assertFalse(artifact.parent.joinpath("payload/src/helper.pyc").exists())
        artifact.write_bytes(b"tampered")
        self.assertFalse(manager.verify(artifact.parent))
        manager.build(project, "directory")
        self.run_artifact(artifact)
        old_hash = artifact.read_bytes()[:512]
        project.entry_path.write_text("broken syntax !!!", encoding="utf-8")
        with self.assertRaises(Exception):
            manager.build(project, "directory")
        self.assertEqual(artifact.read_bytes()[:512], old_hash)
        self.assertTrue(manager.verify(artifact.parent))
        self.assertFalse(list(artifact.parent.parent.glob("_staging-*")))

    def test_single_exe_runs_alone_incremental(self):
        project = self.project()
        manager = self.manager()
        start = time.monotonic()
        first = manager.build(project, "standalone")
        artifact = Path(first["artifact"])
        only = self.temp / "only-exe"
        only.mkdir()
        portable = only / artifact.name
        shutil.copy2(artifact, portable)
        self.run_artifact(portable)
        self.assertEqual([p.name for p in only.iterdir()], [artifact.name])
        self.assertTrue(manager.build(project, "standalone")["cache_hit"])
        project.entry_path.write_text(project.entry_path.read_text(encoding="utf-8") + "\nprint('changed')\n", encoding="utf-8")
        changed = manager.build(project, "standalone")
        self.assertEqual(changed["changed"], ["src/main.py"])
        self.run_artifact(Path(changed["artifact"]))

    def test_javascript_typescript_single_exe_and_imports(self):
        for language in ("javascript", "typescript"):
            with self.subTest(language=language):
                project = self.project(language, language)
                extension = "js" if language == "javascript" else "ts"
                project.root.joinpath(f"src/helper.{extension}").write_text("module.exports = {value: 42};\n", encoding="utf-8")
                original = project.entry_path.read_text(encoding="utf-8")
                if language == "typescript":
                    original = "const typedValue: number = 42; console.log(typedValue);\n" + original
                project.entry_path.write_text("const helper = require('./helper'); console.log(helper.value);\n" + original, encoding="utf-8")
                manager = self.manager()
                built = manager.build(project, "standalone")
                report = self.run_artifact(Path(built["artifact"]))
                self.assertIn("42", report["output"])
                self.assertTrue(manager.build(project, "standalone")["cache_hit"])

    def test_vision_profile_real_ocr_in_frozen_exe(self):
        from PIL import Image, ImageDraw, ImageFont
        project = self.project("vision")
        project.manifest["modules"] = ["vision"]
        project.save_manifest()
        image_path = project.root / "resources/ocr.png"
        with Image.new("RGB", (500, 100), "white") as image:
            ImageDraw.Draw(image).text((15,15), "PCIDE 2026", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40))
            image.save(image_path)
        project.entry_path.write_text(project.entry_path.read_text(encoding="utf-8") +
            "\nfrom pcide.runtime_api import ocr\nprint(ocr('resources/ocr.png'))\n", encoding="utf-8")
        manager = self.manager()
        built = manager.build(project, "standalone")
        report = self.run_artifact(Path(built["artifact"]))
        self.assertIn("PCIDE", report["output"])
        self.assertIn("2026", report["output"])

    def test_frozen_python_native_dotnet_plugins(self):
        from pcide.core.plugins import write_example_plugins
        project = self.project("plugins")
        write_example_plugins(project.root)
        project.entry_path.write_text(project.entry_path.read_text(encoding="utf-8") +
            "\nfrom pathlib import Path\nfrom pcide.core.plugins import PluginRegistry\n"
            "registry = PluginRegistry(Path.cwd(), ['vision.simulated', 'native.example'])\n"
            "try:\n    for plugin in registry.discover():\n        print(registry.call(plugin.id, plugin.capabilities[0]))\n"
            "finally:\n    registry.close()\n", encoding="utf-8")
        built = self.manager().build(project, "standalone")
        report = self.run_artifact(Path(built["artifact"]))
        self.assertIn("dotnet", report["output"])
        self.assertIn("42", report["output"])

    def test_frozen_public_routines_locals_data_and_metadata_cache_invalidation(self):
        from pcide.core.paths import atomic_write_json
        for language, extension in [('python','py'),('zhxb','zhxb'),('javascript','js'),('typescript','ts')]:
            with self.subTest(language=language):
                project = self.project('metadata-'+language, language)
                original = project.entry_path.read_text(encoding='utf-8')
                project.entry_path.write_text(original + ('\n输出(add(count))\n' if language=='zhxb' else '\nprint(add(count))\n' if language=='python' else '\nconsole.log(add(count));\n'), encoding='utf-8')
                library = project.root/f'src/library.{extension}'
                library.write_text('.版本 2\n.子程序 add(value), 整数型, 公开\n返回(value + local_value)\n' if language=='zhxb' else
                                   'def add(value):\n    return value + local_value\n' if language=='python' else
                                   'function add(value) { return value + local_value; }\n', encoding='utf-8')
                metadata = {'public': {'file': f'src/library.{extension}', 'line': 2 if language=='zhxb' else 1,
                                      'sourceName': 'add', 'name':'add', 'public':True,
                                      'locals':[{'name':'local_value','type':'整数型','defaultValue':'7'}]}}
                atomic_write_json(project.ide_dir/'routines.json',metadata)
                project.save_data({'variables':[{'id':'count','label':'数量','type':'整数型','default':'2','scope':'global'}]})
                manager = self.manager()
                built = manager.build(project,'directory')
                def run(expected):
                    report = self.temp / ('metadata-'+language+'.json')
                    environment = os.environ.copy()
                    environment.update(PCIDE_DATA_ROOT=str(self.temp/'execution-cache'), PYTHONPATH='')
                    result = subprocess.run([built['artifact'],'--verify','--report',str(report)],cwd=self.temp,env=environment,
                                            capture_output=True,text=True,encoding='utf-8',timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn(str(expected),json.loads(report.read_text(encoding='utf-8'))['output'])
                run(9)
                self.assertTrue(manager.build(project,'directory')['cache_hit'])
                metadata['public']['locals'][0]['defaultValue']='8'
                atomic_write_json(project.ide_dir/'routines.json',metadata)
                built = manager.build(project,'directory')
                self.assertFalse(built['cache_hit'])
                run(10)

