from __future__ import annotations
import json
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from websockets.sync.server import serve
from pcide.core.dex_bridge import DexBridge, DexBridgeError, browse_dex
from pcide.core.paths import Paths


@contextmanager
def protocol_fixture(response):
    def handler(connection):
        request = json.loads(connection.recv())
        connection.send(json.dumps(response(request)))
    with serve(handler, "127.0.0.1", 0, max_size=65536) as server:
        port = server.socket.getsockname()[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            yield DexBridge(f"ws://127.0.0.1:{port}", timeout=.5)
        finally:
            server.shutdown()
            thread.join(3)


class DexTests(unittest.TestCase):
    def test_compiled_android_index(self):
        result = browse_dex(Paths().root / "runtime/hosts/android/classes.dex")
        self.assertIn("Lpcide/android/RemoteHost;", result["classes"])
        self.assertEqual(result["execution"], "Android ART only")

    def test_transport_request_ownership_and_failure(self):
        with protocol_fixture(lambda q: {"id": q["id"], "runtime": "android-art", "ok": True, "result": {"fixture": True}}) as bridge:
            self.assertTrue(bridge.request("host.describe")["result"]["fixture"])
        for response in (lambda q: {"id": "wrong", "runtime": "android-art", "ok": True},
                         lambda q: {"id": q["id"], "runtime": "windows", "ok": True},
                         lambda q: {"id": q["id"], "runtime": "android-art", "ok": False, "error": "rejected"}):
            with protocol_fixture(response) as bridge:
                with self.assertRaises(DexBridgeError):
                    bridge.request("dex.call")
        with self.assertRaises(DexBridgeError):
            DexBridge("ws://127.0.0.1:1", timeout=.1).request("host.describe")


if __name__ == "__main__":
    unittest.main()
