"""Generic PC script IDE core package.

The package is deliberately independent from the legacy business application.
It owns project files, the form model, script execution, plugins, vision mocks,
and incremental build metadata.
"""

from .paths import IDE_VERSION, Paths

__all__ = ["IDE_VERSION", "Paths"]
from .product import capability_summary, resolve_subsystems, subsystem_catalog
from .agent import AgentSession, AgentTask, AgentState, AgentError, ToolSpec, WorkspaceGuard
from .agent_client import AgentClient, ChatReply
from .compiler import CompilerError, emit_python, lex, parse
from .database import DatabaseError, create_schema, generate_crud, generate_python_module, validate_schema
from .api_center import ApiError, Endpoint, generate_client, generate_client_module, validate_endpoint
from .ai_runtime import AiRuntimeError, ModelSpec, RuntimeSession, VisionProvider, validate_model
from .game_sdk import GameError, Scene, validate_scene
from .agent_roles import role_catalog
from .plugin_market import MarketError, install_archive, uninstall_plugin, rollback_plugin, upgrade_archive, validate_catalog
from .unity import UnityError, UnityProject, bridge_manifest, generate_monobehaviour, inspect_project, scene_descriptor, write_generated_script

__all__ = ["capability_summary", "resolve_subsystems", "subsystem_catalog", "AgentSession", "AgentTask", "AgentState", "AgentError", "ToolSpec", "WorkspaceGuard", "AgentClient", "ChatReply", "CompilerError", "emit_python", "lex", "parse", "DatabaseError", "create_schema", "generate_crud", "generate_python_module", "validate_schema", "ApiError", "Endpoint", "generate_client", "generate_client_module", "validate_endpoint", "AiRuntimeError", "ModelSpec", "RuntimeSession", "VisionProvider", "validate_model", "GameError", "Scene", "validate_scene", "role_catalog", "MarketError", "install_archive", "uninstall_plugin", "upgrade_archive", "rollback_plugin", "validate_catalog", "UnityError", "UnityProject", "bridge_manifest", "generate_monobehaviour", "inspect_project", "scene_descriptor", "write_generated_script"]
