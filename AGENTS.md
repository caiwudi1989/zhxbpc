# PC Script IDE Engineering Rules

- Source root is `F:\PC端软件`. This project has no game or cloud business dependency.
- Entry: `start_ide.ps1` / `src/pcide/main.py`. Read `docs/PROJECT_MEMORY.md` and `docs/index/index_root.md` first.
- Keep source in `src`, tests in `tests`, documentation in `docs`, examples in `examples`.
- Third party editor assets belong to `third_party`; downloads to `downloads`; SDKs to `sdk`; environments to `runtime`; all disposable output to `cache`; EXE delivery to `build`.
- Never modify `D:\zhxbapp`. Extract only directly reviewed generic code and record provenance.
- Script, native plugin, training, and Android hosts are owned child processes with bounded output, timeout, cancellation, and shutdown cleanup. DLL code never enters the IDE process.
- Keep project manifests and form/flow schemas explicit. Reject malformed paths, duplicate IDs, and unsupported execution modes.
- After changes update memory, module index, and verification evidence. Do not claim simulated tests prove hardware, Android, production OCR/YOLO, or clean-machine deployment.
- Do not create or delegate to subagents.
