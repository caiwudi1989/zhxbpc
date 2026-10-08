from __future__ import annotations

import hashlib
import json
import mmap
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_DEX_BYTES = 64 * 1024 * 1024
MAX_BRIDGE_BYTES = 1024 * 1024


class DexBridgeError(RuntimeError):
    pass


@dataclass
class DexBridge:
    url: str = "ws://127.0.0.1:8765"
    timeout: float = 3.0

    def request(self, method, params=None):
        if not isinstance(method, str) or not method or len(method) > 128:
            raise DexBridgeError("invalid remote method")
        import websocket
        request_id = uuid.uuid4().hex
        payload = json.dumps({"id": request_id, "protocol": "pcide-dex-v1", "method": method, "params": params or {}})
        connection = None
        try:
            connection = websocket.create_connection(self.url, timeout=self.timeout, enable_multithread=False)
            connection.send(payload)
            raw = connection.recv()
            if not isinstance(raw, str) or len(raw) > MAX_BRIDGE_BYTES:
                raise DexBridgeError("invalid/oversized Android host response")
            result = json.loads(raw)
            if result.get("id") != request_id or result.get("runtime") != "android-art":
                raise DexBridgeError("response is not owned by this Android ART request")
            if not result.get("ok"):
                raise DexBridgeError(result.get("error", "Android host call failed"))
            return result
        except (OSError, ValueError, websocket.WebSocketException) as exc:
            raise DexBridgeError(f"Android DEX host unavailable: {exc}") from exc
        finally:
            if connection:
                connection.close()


def browse_dex(path):
    source = Path(path)
    size = source.stat().st_size
    if not 112 <= size <= MAX_DEX_BYTES:
        raise DexBridgeError("DEX file size outside supported range")
    with source.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if data[:4] != b"dex\n" or data[7] != 0:
            raise DexBridgeError("not a standard DEX file")
        version = data[4:7].decode("ascii")
        file_size, header_size, endian = struct.unpack_from("<III", data, 32)
        if file_size != size or header_size != 112 or endian != 0x12345678:
            raise DexBridgeError("invalid DEX header/endianness")
        string_count, string_offset = struct.unpack_from("<II", data, 56)
        type_count, type_offset = struct.unpack_from("<II", data, 64)
        class_count, class_offset = struct.unpack_from("<II", data, 96)
        for count, offset, width in ((string_count, string_offset, 4), (type_count, type_offset, 4), (class_count, class_offset, 32)):
            if count > 1000000 or offset + count * width > size:
                raise DexBridgeError("DEX section escapes file")
        def string_at(index):
            if index >= string_count:
                raise DexBridgeError("invalid DEX string index")
            offset = struct.unpack_from("<I", data, string_offset + index * 4)[0]
            if offset >= size:
                raise DexBridgeError("DEX string offset escapes file")
            for _ in range(5):
                if offset >= size:
                    raise DexBridgeError("truncated DEX ULEB128")
                byte = data[offset]
                offset += 1
                if not byte & 0x80:
                    break
            else:
                raise DexBridgeError("invalid DEX ULEB128")
            end = data.find(b"\0", offset, min(size, offset + 65536))
            if end < 0:
                raise DexBridgeError("unterminated DEX string")
            # Class descriptors are ASCII. Other modified UTF-8 strings are
            # presented as escaped byte data, never used as executable names.
            return data[offset:end].decode("utf-8", errors="backslashreplace")
        classes = []
        for index in range(min(class_count, 10000)):
            type_index = struct.unpack_from("<I", data, class_offset + index * 32)[0]
            if type_index >= type_count:
                raise DexBridgeError("invalid DEX type index")
            string_index = struct.unpack_from("<I", data, type_offset + type_index * 4)[0]
            classes.append(string_at(string_index))
        return {"format": "DEX", "version": version, "bytes": size, "class_count": class_count,
                "classes": classes, "sha256": hashlib.sha256(data).hexdigest(), "execution": "Android ART only"}
