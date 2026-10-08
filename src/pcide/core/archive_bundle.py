"""Reuses the pinned PyInstaller runtime archive, compressing only project files."""
from __future__ import annotations

import shutil
import struct
from pathlib import Path


_ALREADY_COMPRESSED = {".7z", ".avi", ".bmp", ".dll", ".exe", ".gif", ".gz", ".ico",
                      ".jpeg", ".jpg", ".mp3", ".mp4", ".onnx", ".pdb", ".png", ".pyd",
                      ".so", ".tar", ".tif", ".tiff", ".webp", ".whl", ".zip"}


def _compress_payload(path: Path) -> bool:
    """Compress small text/bytecode files, but stream binary payloads as-is.

    Native/.NET libraries and model/media files are already dense. Passing
    those through zlib made every incremental standalone build spend several
    seconds in compression with negligible size savings. Small manifests and
    bytecode still benefit from compression.
    """
    try:
        if path.suffix.lower() in _ALREADY_COMPRESSED:
            return False
        return path.stat().st_size <= 512 * 1024
    except OSError:
        return False


def embed_payload(base_exe, payload_root, output, scratch):
    from PyInstaller.archive.readers import CArchiveReader
    from PyInstaller.archive.writers import CArchiveWriter
    base = CArchiveReader(str(base_exe))
    extra_path = Path(scratch) / "payload.pkg"
    entries = [(p.relative_to(payload_root).as_posix(), str(p), _compress_payload(p), "x")
               for p in sorted(Path(payload_root).rglob("*"))
               if p.is_file() and (p.relative_to(payload_root).parts[0] == "payload" or p.name == "package.json")]
    CArchiveWriter(str(extra_path), entries, "python312.dll")
    extra = CArchiveReader(str(extra_path))
    def cookie_for(reader, filename):
        with open(filename, "rb") as source:
            source.seek(reader._end_offset - CArchiveWriter._COOKIE_LENGTH)
            return list(struct.unpack(CArchiveWriter._COOKIE_FORMAT, source.read(CArchiveWriter._COOKIE_LENGTH)))
    cookie = cookie_for(base, base_exe)
    base_toc, extra_toc = cookie[2], cookie_for(extra, extra_path)[2]
    original = [(offset, length, size, compression, kind, name)
                for name, (offset, length, size, compression, kind) in base.toc.items()]
    original += [(0, 0, 0, 0, "o", option) for option in base.options]
    appended = [(base_toc + offset, length, size, compression, kind, name)
                for name, (offset, length, size, compression, kind) in extra.toc.items()]
    toc = CArchiveWriter._serialize_toc(original + appended)
    with open(base_exe, "rb") as source, open(output, "wb") as destination:
        remaining = base._start_offset + base_toc
        while remaining:
            data = source.read(min(1024 * 1024, remaining))
            if not data:
                raise ValueError("truncated frozen runtime")
            destination.write(data)
            remaining -= len(data)
        with extra_path.open("rb") as added:
            remaining = extra_toc
            while remaining:
                data = added.read(min(1024 * 1024, remaining))
                destination.write(data)
                remaining -= len(data)
        toc_offset = base_toc + extra_toc
        destination.write(toc)
        cookie[1:4] = [toc_offset + len(toc) + CArchiveWriter._COOKIE_LENGTH, toc_offset, len(toc)]
        destination.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, *cookie))
    extra_path.unlink()
