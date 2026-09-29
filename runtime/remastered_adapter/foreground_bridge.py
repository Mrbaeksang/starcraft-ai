"""Persistent foreground screen/input transport for the installed Remastered client.

The protocol is JSON lines over a PowerShell child process. It exposes pixels
and UI input; it does not expose game objects or implement a playing policy.
"""

from __future__ import annotations

import json
import os
import queue
import re
import struct
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Frame:
    path: Path
    sequence: int
    capture_ms: float
    width: int
    height: int


def local_path(windows_path: str) -> Path:
    if os.name == "nt":
        return Path(windows_path)
    if not os.environ.get("WSL_DISTRO_NAME"):
        raise RuntimeError("The foreground bridge requires Windows or WSL")
    match = re.fullmatch(r"([A-Za-z]):\\(.*)", windows_path)
    if match is None:
        raise ValueError("The bridge returned a non-drive Windows path")
    drive, tail = match.groups()
    if any(part in ("", ".", "..") for part in tail.split("\\")):
        raise ValueError("The bridge returned an invalid frame path")
    return Path("/mnt", drive.lower(), *tail.split("\\"))


def windows_path(path: Path) -> str:
    if os.name == "nt":
        return str(path.resolve())
    if not os.environ.get("WSL_DISTRO_NAME"):
        raise RuntimeError("The foreground bridge requires Windows or WSL")
    return subprocess.check_output(
        ["wslpath", "-w", str(path.resolve())], text=True, timeout=3
    ).strip()


class ForegroundBridge:
    def __init__(
        self,
        script: Path,
        timeout: float = 3.0,
        command: Sequence[str] | None = None,
        manifest: Path | None = None,
    ) -> None:
        self.timeout = timeout
        manifest = manifest or Path(__file__).parent / "manifests/1.23.10.13515.json"
        expected = json.loads(manifest.read_text(encoding="utf-8"))
        if expected.get("schema") != "scai-remastered-client-v1":
            raise ValueError("Unsupported client manifest")
        self._lock = threading.Lock()
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._process = subprocess.Popen(
            list(command)
            if command is not None
            else [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                windows_path(script),
                "-ManifestPath",
                windows_path(manifest),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        assert self._process.stdout is not None
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        try:
            ready = self._receive()
            if ready.get("event") != "ready" or not ready.get("ok"):
                raise RuntimeError("The foreground bridge did not become ready")
            if (
                ready.get("client_version") != expected["version"]
                or ready.get("client_sha256") != expected["sha256"]
            ):
                raise RuntimeError("The foreground bridge reported a different client build")
            self.pid = int(ready["pid"])
            self.hwnd = int(ready["hwnd"])
            self.width = int(ready["width"])
            self.height = int(ready["height"])
            if min(self.pid, self.hwnd, self.width, self.height) <= 0:
                raise RuntimeError("The bridge returned invalid window identity")
            self._sequence = 0
        except BaseException:
            self.close()
            raise

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _receive(self) -> dict[str, Any]:
        try:
            line = self._lines.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TimeoutError("The foreground bridge did not respond") from exc
        if line is None:
            raise RuntimeError("The foreground bridge exited")
        try:
            result = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The foreground bridge returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise RuntimeError("The foreground bridge returned a non-object")
        return result

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._process.poll() is not None or self._process.stdin is None:
                raise RuntimeError("The foreground bridge is closed")
            self._process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self._process.stdin.flush()
            try:
                result = self._receive()
            except (TimeoutError, RuntimeError):
                self._process.kill()
                raise
            if result.get("op") != payload["op"]:
                raise RuntimeError("The foreground bridge response is out of order")
            if not result.get("ok"):
                raise RuntimeError(str(result.get("error", "The foreground bridge rejected input")))
            return result

    def capture(self) -> Frame:
        result = self._request({"op": "capture"})
        sequence = int(result["sequence"])
        width, height = int(result["width"]), int(result["height"])
        if sequence != self._sequence + 1 or (width, height) != (self.width, self.height):
            raise RuntimeError("Frame sequence or dimensions changed")
        path = local_path(str(result["path"]))
        with path.open("rb") as image:
            header = image.read(24)
        if (
            len(header) != 24
            or header[:8] != b"\x89PNG\r\n\x1a\n"
            or header[12:16] != b"IHDR"
            or struct.unpack(">II", header[16:24]) != (width, height)
        ):
            raise RuntimeError("The bridge frame is not the expected PNG")
        self._sequence = sequence
        return Frame(path, sequence, float(result["capture_ms"]), width, height)

    def click(self, x: int, y: int, button: str = "left") -> float:
        if button not in ("left", "right"):
            raise ValueError("Unsupported mouse button")
        result = self._request({"op": "click", "x": x, "y": y, "button": button})
        if (int(result["x"]), int(result["y"]), result["button"]) != (x, y, button):
            raise RuntimeError("The bridge reported a different click target")
        return float(result["input_ms"])

    def keys(self, virtual_keys: list[int]) -> float:
        result = self._request({"op": "keys", "vks": virtual_keys})
        return float(result["input_ms"])

    def close(self) -> None:
        if self._process.poll() is None:
            try:
                self._request({"op": "quit"})
                self._process.wait(timeout=1)
            except (OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
                self._process.kill()
                self._process.wait(timeout=1)
        for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
            if stream is not None:
                stream.close()

    def __enter__(self) -> ForegroundBridge:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
