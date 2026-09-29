"""A narrow, player-visible I/O probe for the current Windows client.

This module does not start matchmaking or claim to control gameplay. It keeps
capture and keyboard input addressed to one verified window handle.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GameWindow:
    hwnd: int
    process_id: int
    title: str
    width: int
    height: int
    is_foreground: bool


@dataclass(frozen=True)
class CaptureProbe:
    window: GameWindow
    output: str
    sha256: str
    captured_width: int
    captured_height: int
    background_window_png_captured: bool
    content_visually_verified: bool = False
    capture_only: bool = True
    mouse_input_verified: bool = False
    gameplay_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _windows_path(path: Path) -> str:
    if os.name == "nt":
        return str(path.resolve())
    if not os.environ.get("WSL_DISTRO_NAME"):
        raise RuntimeError("The Remastered window probe requires Windows or WSL2")
    result = subprocess.run(
        ["wslpath", "-w", str(path.resolve())],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


class WinAppWindow:
    """Use Microsoft's winapp CLI without activating the target window."""

    def __init__(self, executable: Path) -> None:
        if not executable.is_file():
            raise FileNotFoundError(executable)
        self.executable = executable

    def _run(self, *arguments: str) -> Any:
        environment = {**os.environ, "WINAPP_CLI_TELEMETRY_OPTOUT": "1"}
        result = subprocess.run(
            [str(self.executable), "ui", *arguments, "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=environment,
        )
        if result.returncode:
            raise RuntimeError(f"winapp CLI failed ({result.returncode}): {result.stderr.strip()}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("winapp CLI did not return one JSON result") from exc

    def find_game_window(self) -> GameWindow:
        payload = self._run("list-windows", "--app", "StarCraft")
        matches = [
            item
            for item in payload
            if item.get("processName") == "StarCraft" and item.get("title") == "Brood War"
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one Brood War window, found {len(matches)}")
        item = matches[0]
        return GameWindow(
            hwnd=int(item["hwnd"]),
            process_id=int(item["processId"]),
            title=str(item["title"]),
            width=int(item["width"]),
            height=int(item["height"]),
            is_foreground=bool(item["isForeground"]),
        )

    def capture(self, window: GameWindow, output: Path) -> CaptureProbe:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.png")
        try:
            payload = self._run(
                "screenshot",
                "--window",
                str(window.hwnd),
                "--output",
                _windows_path(temporary_output),
            )
            if (
                int(payload["hwnd"]) != window.hwnd
                or int(payload["processId"]) != window.process_id
            ):
                raise RuntimeError("Capture target changed")
            if not temporary_output.is_file():
                raise RuntimeError("The game window was not captured")
            image = temporary_output.read_bytes()
            if len(image) < 24 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
                raise RuntimeError("The capture is not a PNG")
            png_width, png_height = struct.unpack(">II", image[16:24])
            if (png_width, png_height) != (int(payload["width"]), int(payload["height"])):
                raise RuntimeError("The captured PNG dimensions do not match the tool result")
            after = self.find_game_window()
            if after.hwnd != window.hwnd or after.process_id != window.process_id:
                raise RuntimeError("Game window changed during capture")
            temporary_output.replace(output)
            return CaptureProbe(
                window=window,
                output=str(output),
                sha256=hashlib.sha256(image).hexdigest(),
                captured_width=png_width,
                captured_height=png_height,
                background_window_png_captured=not window.is_foreground and not after.is_foreground,
            )
        finally:
            temporary_output.unlink(missing_ok=True)

    def send_background_keys(self, window: GameWindow, keys: str) -> None:
        """Send keys to the selected HWND; callers must verify the visible effect."""
        if not keys.strip():
            raise ValueError("keys must not be empty")
        before = self.find_game_window()
        if before.hwnd != window.hwnd or before.process_id != window.process_id:
            raise RuntimeError("Game window changed before keyboard input")
        if before.is_foreground:
            raise RuntimeError("The target game window is foreground")
        payload = self._run(
            "send-keys",
            keys,
            "--window",
            str(window.hwnd),
            "--via",
            "post-message",
        )
        if int(payload["hwnd"]) != window.hwnd or int(payload["actionCount"]) < 1:
            raise RuntimeError("Keyboard input was not accepted by winapp CLI")
        after = self.find_game_window()
        if after.hwnd != window.hwnd or after.process_id != window.process_id:
            raise RuntimeError("Game window changed after keyboard input")
        if after.is_foreground:
            raise RuntimeError("The input operation foregrounded the game")
