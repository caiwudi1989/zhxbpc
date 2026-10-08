from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env.update(DOTNET_CLI_HOME=str(root / "cache" / "dotnet-home"), DOTNET_NOLOGO="1",
           DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1", DOTNET_CLI_TELEMETRY_OPTOUT="1",
           NUGET_PACKAGES=str(root / "cache" / "nuget"))


def main():
    native_output = root / "runtime/modules/native_math/native_math.dll"
    native_output.parent.mkdir(parents=True, exist_ok=True)
    compiler = root / "sdk" / "mingw64" / "bin" / "gcc.exe"
    # MinGW's assembler cannot reliably handle Unicode TEMP/command paths.
    # A transient DOS mapping stays on the same physical workspace.
    drive = next((f"{letter}:" for letter in "ZYXWVUTSRQP" if not Path(f"{letter}:\\").exists()), None)
    if drive is None:
        raise RuntimeError("no temporary DOS drive available for MinGW")
    subprocess.run(["subst", drive, str(root)], check=True)
    try:
        mapped = Path(drive + "\\")
        native_env = env.copy()
        native_env["TEMP"] = str(mapped / "cache" / "temp")
        native_env["TMP"] = native_env["TEMP"]
        subprocess.run([str(mapped / compiler.relative_to(root)), "-shared", "-O2", "-nostdlib",
                       "-Wl,--entry,0", "-L", str(mapped / "sdk" / "mingw64" / "x86_64-w64-mingw32" / "lib"),
                       "-o", str(mapped / native_output.relative_to(root)),
                       str(mapped / "src" / "hosts" / "native_math.c"), "-lkernel32", "-lmsvcrt"],
                       check=True, timeout=60, env=native_env, cwd=mapped)
    finally:
        subprocess.run(["subst", drive, "/D"], check=True)
    dotnet = root / "sdk" / "dotnet" / "dotnet.exe"
    for folder, output in (("dotnet", root / "runtime" / "hosts" / "dotnet"),
                           ("dotnet_example", root / "runtime/modules/dotnet_math")):
        project = root / "src" / "hosts" / folder
        cache = root / "cache" / "build" / folder
        subprocess.run([str(dotnet), "build", str(project), "-c", "Release", "-o", str(output),
             f"-p:BaseIntermediateOutputPath={cache / 'obj'}/", f"-p:MSBuildProjectExtensionsPath={cache / 'obj'}/"],
             check=True, env=env, timeout=90)
    project = root / "src/hosts/dotnet"
    cache = root / "cache/build/dotnet-publish"
    subprocess.run([str(dotnet), "publish", str(project), "-c", "Release", "-r", "win-x64",
                    "--self-contained", "true", "-o", str(root / "runtime/modules/dotnet-host"),
                    "-p:DebugType=None", "-p:DebugSymbols=false",
                    f"-p:BaseOutputPath={cache / 'bin'}/",
                    f"-p:BaseIntermediateOutputPath={cache / 'obj'}/", f"-p:MSBuildProjectExtensionsPath={cache / 'obj'}/"],
                    check=True, env=env, timeout=180)
    print("native and AssemblyLoadContext hosts built")


if __name__ == "__main__":
    main()
