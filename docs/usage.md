# PCIDE

## Entry

- Frozen IDE: `F:\PC端软件\build\PCIDE\PCIDE.exe`.
- Source IDE: `F:\PC端软件\start_ide.cmd`; development interpreter is isolated in `runtime/dev`.
- Projects: `projects/<name>`; source `src`, form `ui/main.form.json`, flow `flows/main.flow.json`, manifest `.pcide/project.json`.
- Verification: `run_tests.ps1`; full command evidence and limits in `archive/verification.md`.

For a frozen installation, `PCIDE.exe --smoke --project <project> --report <json>` checks the script, flow, Monaco assets, and UI updates. Add `--build` to create the standalone customer EXE through the selected runtime profile. `--ui-smoke --screenshot <png> --report <json>` checks the frozen Qt/Monaco surface. These checks use owned child processes with bounded output and finite project timeouts.

## Project Configuration

| Setting | Contract |
| --- | --- |
| `language` | `python`, `javascript`, `typescript` |
| `entry` | Existing relative script path inside the project |
| `modules` | `[]` for basic Python or Node; `["vision"]` for Python OCR/ONNX runtime |
| `execution.timeout_seconds` | Finite positive seconds, maximum 86400 |
| `execution.max_output_lines` | 1..50000 session records |
| `permissions` | Explicit plugin grants; examples use `vision.simulated` or `native.example` |

The project tree exposes `project.json`; changes are validated when saved. Running sessions must end before execution settings are replaced.

## Execution and Build

- Runtime form events call script functions and update controls through `ui.set`; scripts can open or close an independent form with `ui.open(window_id)` and `ui.close(window_id)`. Python imports `pcide.runtime_api`; JS/TS requires `pcide`. Window IDs accept the stable form path key, filename, or unique form ID/title.
- Python uses bdb; JS/TS uses the Node inspector. Breakpoints, stepping, locals and call stacks belong to one process/session. Session records are stored under `cache/sessions`.
- Customer build creates a standalone EXE in `build/artifacts/<project>` using the precompiled runtime. `BuildManager.build(project, "directory")` creates a diagnostic directory instead. Customer payload contains bytecode and selected resources; basic builds exclude development environment and source.
- Project Python libraries must be provided by a selected prebuilt profile or bundled project code. Arbitrary pip dependencies and arbitrary Node packages are not automatically packaged.
- Each `ui/**/*.form.json` is an independent window. The window contract includes maximize/minimize/resizable flags, fixed or bounded dimensions, anchor/dock policy, and auto-fill. `Project.window_paths()` lists windows with `ui/main.form.json` first; the runtime manager opens and closes them by stable path ID.
- `.pcide/data.json` stores variables with `global`, `window`, `module`, or `local` scope, constants, and DLL/SDK/API records with parameters, return type, calling convention, permissions, and dependencies. Chinese `label` values are paired with ASCII `id` values; `core.data.generate_code()` emits Python, JavaScript, or TypeScript declarations and API stubs.
- Build provenance is `build.json`; it is not required next to the portable standalone EXE. `--verify --report <path>` executes startup and registered click handlers for controlled validation.
- Bytecode is not encryption. JS source reflection, unusual module layouts and dependencies must be validated before distribution.

## Extensions and Vision

- Python, C ABI and .NET plugins run in separate processes. .NET host is self-contained in `runtime/modules/dotnet-host`; developer SDK is used only during host builds.
- Example plugin manifests/sources are in `examples/plugins`; compiled libraries are in `runtime/modules`. The project must explicitly grant their declared permissions.
- Vision datasets remain in each project; models are `runtime/models/<project-id>`, logs `cache/training/<project-id>`. The sample mocks remain marked `simulated`.
- OCR uses RapidOCR/ONNX Runtime. YOLO tests support Ultralytics detect ONNX tensors. CPU training/export uses optional `runtime/training` and explicit model files; small synthetic verification establishes execution, not model accuracy.
- Win32/COM/UIA, serial and HID API entry points are exposed in `pcide.runtime_api`. Serial loopback and device enumeration are software checks, not hardware integration acceptance.

## Android

- Host `runtime/hosts/android/classes.dex`; example `runtime/hosts/android/example/classes.dex`. They were compiled using the copied JDK/Android tools under `sdk`.
- PC browses DEX classes; execution requires an Android device running `pcide.android.RemoteHost` and an explicitly forwarded WebSocket endpoint. Default bridge endpoint is loopback port 8765.
- This machine reported no connected ADB device. PC WebSocket fixture tests verify transport/error ownership only. Android ART execution remains unverified.
