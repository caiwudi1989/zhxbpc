from __future__ import annotations

import hashlib
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = Path("D:/zhxbapp/运行环境/APP")
DEPENDENCIES = ("org/java-websocket/Java-WebSocket/1.6.0/Java-WebSocket-1.6.0.jar",
                "org/slf4j/slf4j-api/2.0.16/slf4j-api-2.0.16.jar",
                "org/slf4j/slf4j-nop/2.0.16/slf4j-nop-2.0.16.jar")


def main():
    jdk = ROOT / "sdk/jdk17"
    if not jdk.exists():
        shutil.copytree(LEGACY / "JDK17", jdk)
    android = ROOT / "sdk/android"
    for relative in ("build-tools/35.0.1/lib/d8.jar", "platforms/android-35/android.jar",
                     "platform-tools/adb.exe", "platform-tools/AdbWinApi.dll", "platform-tools/AdbWinUsbApi.dll"):
        destination = android / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(LEGACY / "Android/sdk" / relative, destination)
    downloads = ROOT / "downloads/android-host"
    downloads.mkdir(parents=True, exist_ok=True)
    jars = []
    for relative in DEPENDENCIES:
        url = "https://repo.maven.apache.org/maven2/" + relative
        target = downloads / Path(relative).name
        if not target.exists():
            urllib.request.urlretrieve(url, target)
        expected = urllib.request.urlopen(url + ".sha1", timeout=30).read().decode().strip()
        if hashlib.sha1(target.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"download hash mismatch: {target.name}")
        jars.append(target)
    cache = ROOT / "cache/build/android"
    classes = cache / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    android_jar = android / "platforms/android-35/android.jar"
    sources = list((ROOT / "src/hosts/android").glob("*.java"))
    subprocess.run([str(jdk / "bin/javac.exe"), "-encoding", "UTF-8", "-source", "8", "-target", "8",
                    "-cp", ";".join(str(j) for j in [android_jar, *jars]), "-d", str(classes), *map(str, sources)], check=True, timeout=60)
    archive = cache / "host-classes.jar"
    with zipfile.ZipFile(archive, "w") as output:
        for path in classes.rglob("*.class"):
            if path.stem == "ExampleDex":
                continue
            output.write(path, path.relative_to(classes).as_posix())
    example_archive = cache / "example.jar"
    with zipfile.ZipFile(example_archive, "w") as output:
        example = classes / "pcide/android/ExampleDex.class"
        output.write(example, example.relative_to(classes).as_posix())
    target = ROOT / "runtime/hosts/android"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(jdk / "bin/java.exe"), "-cp", str(android / "build-tools/35.0.1/lib/d8.jar"),
                    "com.android.tools.r8.D8", "--min-api", "26", "--lib", str(android_jar),
                    "--output", str(target), str(archive), *map(str, jars)], check=True, timeout=60)
    example_output = target / "example"
    example_output.mkdir(exist_ok=True)
    subprocess.run([str(jdk / "bin/java.exe"), "-cp", str(android / "build-tools/35.0.1/lib/d8.jar"),
                    "com.android.tools.r8.D8", "--min-api", "26", "--lib", str(android_jar),
                    "--output", str(example_output), str(example_archive)], check=True, timeout=60)
    subprocess.run([str(android / "platform-tools/adb.exe"), "devices", "-l"], check=True, timeout=15)
    print("Android host DEX:", target / "classes.dex")


if __name__ == "__main__":
    main()
