"""Engine file factories and argument-vector commands; no in-process engine code."""
from __future__ import annotations

from pathlib import Path

def bind_engine_project(paths, name, template_id, root, tools=None):
    """Create an IDE reference project without changing existing engine assets."""
    from .development import TEMPLATE_MAP, create_project, validate_development
    from .paths import atomic_write_json
    template = TEMPLATE_MAP.get(template_id)
    if template is None or template.mode != 'engine':
        raise ValueError('只能绑定 Unity/Godot 引擎模板')
    settings = validate_development({'template': template_id, 'tools': tools or {}}, template.language)
    root = Path(root).resolve()
    if template_id.startswith('unity-'):
        from .unity import bridge_manifest, inspect_project
        unity = inspect_project(root)
        bridge = {**bridge_manifest(unity), 'project_root': str(unity.root)}
    elif not (root / 'project.godot').is_file() or (root / 'project.godot').is_symlink():
        raise ValueError('Godot 工程缺少 project.godot')
    project = create_project(paths, name, template_id)
    project.manifest['development'].update(engine_root=str(root), tools=settings['tools'])
    project.save_manifest()
    if template_id.startswith('unity-'):
        atomic_write_json(project.root / 'game/unity_bridge.json', bridge)
    (project.root / 'README.md').write_text(
        f'# {name}\n\n已绑定已有 {template.label}：`{root}`\n\n'
        'F5运行/打开引擎，游戏引擎菜单打开编辑器，Ctrl+B构建Windows游戏。\n'
        '环境 → 系统工具与游戏引擎配置已有引擎程序。\n'
        '外部工程源码与场景在引擎编辑器中编辑；此目录只保存IDE配置和模板参考。\n'
        'Unity构建使用外部工程的Build Settings场景；Godot需Windows Desktop导出预设。\n',
        encoding='utf-8')
    return project

def engine_root(project):
    from .development import template_for
    template = template_for(project)
    root = Path(project.manifest['development'].get('engine_root') or project.root)
    if template.id.startswith('unity-'):
        from .unity import inspect_project
        return inspect_project(root).root
    if not (root / 'project.godot').is_file() or (root / 'project.godot').is_symlink():
        raise ValueError('Godot 工程缺少 project.godot')
    return root.resolve()

def engine_command(project, executable, action, output=None):
    from .development import template_for
    root = engine_root(project)
    template = template_for(project)
    if template.id.startswith('unity-'):
        jobs = str(project.manifest['development']['jobs'])
        command = [executable, '-projectPath', str(root), '-logFile', '-', '-job-worker-count', jobs,
                   '-desiredWorkerCount', jobs, '-standbyWorkerCount', '0']
        if action == 'editor':
            return command
        if action != 'build' or output is None:
            raise ValueError('Unity 支持编辑器启动与 Windows 构建；在编辑器中按 Play 运行')
        if root != project.root:
            return command + ['-batchmode', '-quit', '-buildWindows64Player', str(output)]
        return command + ['-batchmode', '-quit', '-executeMethod', 'PCIDEBuild.BuildWindows', '-pcideOutput', str(output)]
    command = [executable, '--path', str(root)]
    if action == 'editor':
        return command + ['--editor']
    if action == 'run':
        return command
    if action != 'build' or output is None or not (root / 'export_presets.cfg').is_file():
        raise ValueError('Godot 导出需要 export_presets.cfg 中的 Windows Desktop 预设')
    return command + ['--headless', '--export-release' if project.manifest['development']['configuration'] == 'Release' else '--export-debug', 'Windows Desktop', str(output)]

def unity_files(three_d=False):
    dimension = 'PrimitiveType.Cube' if three_d else 'PrimitiveType.Quad'
    rotation = '0f, speed * Time.deltaTime, 0f' if three_d else '0f, 0f, speed * Time.deltaTime'
    camera_settings = ('camera.transform.position = new Vector3(0, 2, -6);' if three_d else
                       'camera.orthographic = true;\n        camera.orthographicSize = 3;\n        camera.transform.position = new Vector3(0, 0, -6);')
    return {
        'Packages/manifest.json': '{"dependencies":{"com.unity.modules.physics":"1.0.0","com.unity.modules.physics2d":"1.0.0","com.unity.modules.inputlegacy":"1.0.0","com.unity.modules.ui":"1.0.0"}}\n',
        'ProjectSettings/ProjectVersion.txt': 'm_EditorVersion: 6000.0.0f1\n',
        'Assets/Scripts/GameController.cs': '''using UnityEngine;
public sealed class GameController : MonoBehaviour {
    public float speed = 60f;
    void Update() { transform.Rotate(''' + rotation + '''); }
}
''',
        'Assets/Editor/PCIDEBuild.cs': '''using System;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
public static class PCIDEBuild {
    [MenuItem("PCIDE/Create Demo Scene")]
    public static void CreateScene() {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene);
        var actor = GameObject.CreatePrimitive(''' + dimension + ''');
        actor.AddComponent<GameController>();
        var camera = new GameObject("Camera").AddComponent<Camera>();
        ''' + camera_settings + '''
        camera.transform.LookAt(actor.transform);
        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.transform.rotation = Quaternion.Euler(40, -30, 0);
        Directory.CreateDirectory("Assets/Scenes");
        EditorSceneManager.SaveScene(scene, "Assets/Scenes/Main.unity");
    }
    public static void BuildWindows() {
        var args = Environment.GetCommandLineArgs();
        var index = Array.IndexOf(args, "-pcideOutput");
        if (index < 0 || index + 1 >= args.Length) throw new ArgumentException("pcideOutput required");
        if (!File.Exists("Assets/Scenes/Main.unity")) CreateScene();
        var report = BuildPipeline.BuildPlayer(new[] { "Assets/Scenes/Main.unity" }, args[index + 1],
            BuildTarget.StandaloneWindows64, BuildOptions.None);
        if (report.summary.result != BuildResult.Succeeded) throw new Exception("Unity build failed");
    }
}
''',
    }

def godot_files(three_d=False):
    scene = ('''[gd_scene load_steps=4 format=3]
[ext_resource type="Script" path="res://src/main.gd" id="1"]
[sub_resource type="BoxMesh" id="Box"]
[sub_resource type="StandardMaterial3D" id="Color"]
albedo_color = Color(0.2, 0.6, 0.9, 1)
[node name="Main" type="Node3D"]
script = ExtResource("1")
[node name="Cube" type="MeshInstance3D" parent="."]
mesh = SubResource("Box")
material_override = SubResource("Color")
[node name="Camera" type="Camera3D" parent="."]
position = Vector3(0, 0, 5)
current = true
[node name="Light" type="DirectionalLight3D" parent="."]
rotation_degrees = Vector3(-35, -30, 0)
''') if three_d else '''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://src/main.gd" id="1"]
[node name="Main" type="Node2D"]
script = ExtResource("1")
'''
    script = ('extends Node3D\n\nfunc _process(delta):\n    $Cube.rotate_y(delta)\n') if three_d else '''extends Node2D
var position_x := 80.0
func _process(delta):
    position_x = fmod(position_x + 100 * delta, 720)
    queue_redraw()
func _draw():
    draw_circle(Vector2(position_x, 220), 30, Color.CORNFLOWER_BLUE)
'''
    return {'project.godot': '[application]\nconfig/name="PCIDE Game"\nrun/main_scene="res://game/main.tscn"\n'
            '[display]\nwindow/size/viewport_width=760\nwindow/size/viewport_height=440\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            'src/main.gd': script, 'game/main.tscn': scene,
            'export_presets.cfg': '[preset.0]\nname="Windows Desktop"\nplatform="Windows Desktop"\n'
            'runnable=true\nexport_filter="all_resources"\ninclude_filter=""\nexclude_filter=".pcide/*,README.md"\n'
            'export_path=""\n[preset.0.options]\nbinary_format/architecture="x86_64"\n'}
