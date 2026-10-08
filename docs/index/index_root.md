# Project Index

- `src/pcide/main.py`: launch, `--smoke`, `--ui-smoke`, Qt IDE entry, and project build smoke.
- `src/pcide/core`: project/form/flow schemas, bounded child process runner, Windows pipe protocol, plugin registry, vision adapters, and incremental builder.
- `src/hosts`: isolated native/.NET/Android host sources; contracts are in `docs/规范`.
- `third_party/monaco`: reviewed Microsoft editor distribution used by the Qt WebEngine editor.
- `tests`: core, automation, DEX, Qt/Monaco, and frozen build gates; final run is in `cache/logs/tests-full-release.log`.
- `tools/freeze_runtime.py`, `tools/freeze_ide.py`: reproducible local runtime and IDE freezes; final logs are in `cache/logs`.
- `tools/verify_release.py`: isolated final frozen IDE/customer/worker lifecycle gate; report is `cache/logs/frozen-release.json`.
- `tools/deliver_examples.py`: example customer EXEs and cache/build timing report in `cache/logs/delivery.json`.
- `architecture.md`: directory/data/entry chains and delivery boundaries.
- `archive/verification.md`: commands, exit status, artifact evidence and limitations.
- [PC Module Index](平台/pc.md)
