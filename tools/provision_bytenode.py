import base64
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = "1.7.0"
with urllib.request.urlopen(f"https://registry.npmjs.org/bytenode/{version}", timeout=30) as response:
    metadata = json.load(response)
archive = root / f"downloads/bytenode-{version}.tgz"
urllib.request.urlretrieve(metadata["dist"]["tarball"], archive)
expected = metadata["dist"]["integrity"].split("-", 1)[1]
if base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode() != expected:
    raise RuntimeError("Bytenode integrity mismatch")
target = root / "third_party/bytenode"
target.mkdir(exist_ok=True)
with tarfile.open(archive) as package:
    for original, name in (("package/lib/index.js", "index.cjs"), ("package/lib/cli.js", "cli.cjs"), ("package/LICENSE", "LICENSE"), ("package/package.json", "package.json")):
        source = package.extractfile(original)
        if source is None:
            raise RuntimeError(f"missing Bytenode file: {original}")
        with source, (target / name).open("wb") as destination:
            shutil.copyfileobj(source, destination)
print("Bytenode", version, "verified:", target)
