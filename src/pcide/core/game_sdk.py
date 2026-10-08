"""Game SDK scene contract; renderers remain isolated providers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

class GameError(ValueError): pass

@dataclass
class Scene:
    id: str
    backend: str = "opengl"
    entities: list[dict[str, Any]] = field(default_factory=list)
    camera: dict[str, Any] = field(default_factory=lambda: {"position": [0, 0, 5], "fov": 60})

def validate_scene(scene: Scene) -> Scene:
    if not isinstance(scene, Scene) or not isinstance(scene.id, str) or not scene.id.strip() or len(scene.id) > 128 or not isinstance(scene.backend, str) or scene.backend.lower() not in {"opengl", "directx", "vulkan", "unity", "unreal", "godot"}:
        raise GameError("场景标识或渲染后端非法")
    if not isinstance(scene.entities, list) or len(scene.entities) > 10000 or any(
        not isinstance(entity, dict) or not isinstance(entity.get("id"), str) or not entity["id"].strip()
        for entity in scene.entities
    ):
        raise GameError("场景实体必须包含非空 id")
    if len({entity["id"] for entity in scene.entities}) != len(scene.entities):
        raise GameError("场景实体 id 不能重复")
    if not isinstance(scene.camera, dict) or not isinstance(scene.camera.get("position"), list) or len(scene.camera["position"]) != 3 or any(type(value) not in {int, float} for value in scene.camera["position"]):
        raise GameError("场景实体或摄像机配置非法")
    if type(scene.camera.get("fov", 60)) not in {int, float} or not 1 <= float(scene.camera.get("fov", 60)) <= 179:
        raise GameError("摄像机视场角非法")
    return scene
