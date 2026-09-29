"""Protocol checks that run without StarCraft or a Windows CI runner."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from foreground_bridge import ForegroundBridge, local_path

FAKE_PROCESS = r"""
import json, sys
print(json.dumps({"ok": True, "event": "ready", "pid": 7,
                  "hwnd": 8, "width": 1, "height": 1,
                  "client_version": "1.23.10.13515",
                  "client_sha256":
                    "ce3ab05dc9a6aa35418947e5d95e19651ad6fbcd5e2c1856cd729c5b7c31281c"}),
      flush=True)
for line in sys.stdin:
    request = json.loads(line)
    op = request["op"]
    if op == "capture":
        result = {"ok": True, "op": op, "path": "C:\\frame.png", "sequence": 1,
                  "width": 1, "height": 1, "capture_ms": 12.5}
    elif op == "click" and request["x"] < 0:
        result = {"ok": False, "error": "client_coordinates"}
    elif op == "click":
        result = {"ok": True, "op": op, "x": request["x"], "y": request["y"],
                  "button": request["button"], "input_ms": 2.5}
    elif op == "focus":
        result = {"ok": True, "op": op, "pid": 7, "hwnd": 8}
    else:
        result = {"ok": True, "op": op, "input_ms": 1.0}
    print(json.dumps(result), flush=True)
    if op == "quit": break
"""


class ForegroundBridgeTest(unittest.TestCase):
    def test_rejects_wrong_client_build(self) -> None:
        wrong_build = FAKE_PROCESS.replace("1.23.10.13515", "1.23.10.99999")
        with self.assertRaisesRegex(RuntimeError, "different client build"):
            ForegroundBridge(Path("unused"), command=[sys.executable, "-u", "-c", wrong_build])

    def test_capture_and_click_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary, "frame.png")
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01" * 2
            )
            with (
                patch("foreground_bridge.local_path", return_value=image),
                ForegroundBridge(
                    Path("unused"), command=[sys.executable, "-u", "-c", FAKE_PROCESS]
                ) as bridge,
            ):
                self.assertEqual((bridge.pid, bridge.hwnd), (7, 8))
                bridge.focus()
                self.assertEqual(bridge.click(0, 0), 2.5)
                self.assertEqual(bridge.click(0, 0, "right"), 2.5)
                with self.assertRaisesRegex(RuntimeError, "client_coordinates"):
                    bridge.click(-1, 0)
                frame = bridge.capture()
                self.assertEqual((frame.path, frame.sequence, frame.capture_ms), (image, 1, 12.5))
                with self.assertRaisesRegex(RuntimeError, "Frame sequence"):
                    bridge.capture()

    def test_wsl_path_rejects_traversal(self) -> None:
        with (
            patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}),
            self.assertRaisesRegex(ValueError, "invalid frame path"),
        ):
            local_path(r"C:\temp\..\frame.png")


if __name__ == "__main__":
    unittest.main()
